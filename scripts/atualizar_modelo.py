#!/usr/bin/env python3
"""
Atualiza o visualizador com novas entradas reais e recalcula correções do modelo.

Como usar:
1. Adicione novas linhas em data/entrada/novos_resultados.csv, usando ; como separador.
2. Rode na raiz do repositório:
   python scripts/atualizar_modelo.py
3. O script atualiza:
   - data/resultados_reais.csv
   - data/neural/correcoes_modelo.csv
   - data/neural/estado_times.csv
   - data/neural/model_state.json
   - src/model-data.js
"""
from pathlib import Path
import json, re, unicodedata, subprocess, sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / 'src' / 'data.js'
PRED_CSV = ROOT / 'data' / 'previsoes_modelo.csv'
REAL_CSV = ROOT / 'data' / 'resultados_reais.csv'
NEW_CSV = ROOT / 'data' / 'entrada' / 'novos_resultados.csv'
STRENGTH_CSV = ROOT / 'data' / 'database' / 'team_strengths.csv'
SIM_CSV = ROOT / 'data' / 'database' / 'simulated_matches.csv'
OUT_CORR = ROOT / 'data' / 'neural' / 'correcoes_modelo.csv'
OUT_STATE = ROOT / 'data' / 'neural' / 'estado_times.csv'
OUT_JSON = ROOT / 'data' / 'neural' / 'model_state.json'
OUT_JS = ROOT / 'src' / 'model-data.js'
OUT_TXT = ROOT / 'data' / 'resultados.txt'

ALIASES = {
    'republica da coreia': 'coreia do sul', 'coreia republica': 'coreia do sul', 'holanda': 'paises baixos',
    'paises baixos': 'paises baixos', 'republica tcheca': 'tchequia', 'tchequia': 'tchequia',
    'rd do congo': 'rd congo', 'rd congo': 'rd congo', 'congo kinshasa': 'rd congo', 'congo dr': 'rd congo',
    'dr congo': 'rd congo', 'turkiye': 'turquia', 'eua': 'estados unidos', 'usa': 'estados unidos'
}

def norm(value):
    value = str(value or '').strip().lower()
    value = unicodedata.normalize('NFD', value)
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    value = re.sub(r'[^a-z0-9 ]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return ALIASES.get(value, value)

def parse_base():
    text = DATA_JS.read_text(encoding='utf-8')
    m = re.search(r'window\.WC2026_DATA = (.*);\s*$', text, re.S)
    return json.loads(m.group(1))

def winner(team1, g1, team2, g2):
    if int(g1) > int(g2): return team1
    if int(g2) > int(g1): return team2
    return 'Empate'

def outcome(g1, g2):
    return '1' if int(g1) > int(g2) else '2' if int(g2) > int(g1) else 'X'

def load_new_results(base_matches):
    if not NEW_CSV.exists() or NEW_CSV.stat().st_size < 10:
        return pd.DataFrame()
    new = pd.read_csv(NEW_CSV, sep=';', encoding='utf-8-sig')
    if new.empty:
        return pd.DataFrame()
    lookup = []
    for _, r in base_matches.iterrows():
        lookup.append({'jogo': int(r['jogo']), 'data': r['data'], 'fase': r['fase'], 't1': r['equipe1'], 't2': r['equipe2'], 'n1': norm(r['equipe1']), 'n2': norm(r['equipe2']), 'set': frozenset([norm(r['equipe1']), norm(r['equipe2'])])})
    rows = []
    for _, r in new.iterrows():
        if pd.isna(r.get('time_1')) or pd.isna(r.get('time_2')): continue
        date = str(r.get('data',''))
        n1, n2 = norm(r['time_1']), norm(r['time_2'])
        candidates = [b for b in lookup if b['data'] == date and b['set'] == frozenset([n1,n2])]
        if not candidates:
            candidates = [b for b in lookup if b['set'] == frozenset([n1,n2])]
        if not candidates:
            print(f"Não encontrei jogo para: {r.get('time_1')} x {r.get('time_2')} em {date}")
            continue
        b = candidates[0]
        g1_in, g2_in = int(r['gols_time_1']), int(r['gols_time_2'])
        if n1 == b['n1']:
            g1, g2 = g1_in, g2_in
        else:
            g1, g2 = g2_in, g1_in
        rows.append({'jogo': b['jogo'], 'data': b['data'], 'fase': b['fase'], 'equipe1': b['t1'], 'equipe2': b['t2'], 'gols1_real': g1, 'gols2_real': g2, 'placar_real': f'{g1}-{g2}', 'vencedor_real': winner(b['t1'], g1, b['t2'], g2), 'status_real': 'Finalizado', 'fonte': r.get('fonte',''), 'placar_original': r.get('placar','')})
    return pd.DataFrame(rows)

def rebuild(real_df):
    sim = pd.read_csv(SIM_CSV, encoding='utf-8-sig')
    sim_by_game = {int(r['jogo']): r for _, r in sim.iterrows()}
    strengths = pd.read_csv(STRENGTH_CSV, encoding='utf-8-sig')
    team_strength = {str(r['selecao']): float(r['forca_modelo_0_100']) for _, r in strengths.iterrows()}
    for t in pd.concat([sim['equipe1'], sim['equipe2']]).dropna().unique():
        if t not in team_strength and not str(t).startswith(('1º ', '2º ', '3º ', 'Vencedor', 'Perdedor')):
            vals = []
            for col, team_col in [('forca_equipe1','equipe1'),('forca_equipe2','equipe2')]:
                vals += sim.loc[sim[team_col] == t, col].dropna().astype(float).tolist()
            if vals: team_strength[t] = sum(vals)/len(vals)
    rating_delta = {team: 0.0 for team in team_strength}
    team_games = {team: 0 for team in team_strength}
    team_prox = {team: [] for team in team_strength}
    learning_rate = 0.18
    corrections = []
    for _, r in real_df.sort_values(['data','jogo']).iterrows():
        pred = sim_by_game.get(int(r['jogo']))
        if pred is None: continue
        p1, p2 = int(pred['gols1_sim']), int(pred['gols2_sim'])
        a1, a2 = int(r['gols1_real']), int(r['gols2_real'])
        o_pred, o_real = outcome(p1,p2), outcome(a1,a2)
        err_total = abs(a1-p1)+abs(a2-p2)
        err_saldo = abs((a1-a2)-(p1-p2))
        outcome_ok = o_pred == o_real
        exact = p1 == a1 and p2 == a2
        proximity = max(0, round(100 - 16*err_total - 18*err_saldo - (0 if outcome_ok else 28), 1))
        margin_delta = (a1-a2) - (p1-p2)
        miss_boost = 0 if outcome_ok else (1 if margin_delta > 0 else -1 if margin_delta < 0 else 0)
        adj = round((margin_delta * 1.25 + miss_boost * 0.75) * learning_rate, 3)
        t1, t2 = str(pred['equipe1']), str(pred['equipe2'])
        if t1 in rating_delta: rating_delta[t1] += adj
        if t2 in rating_delta: rating_delta[t2] -= adj
        for t in [t1,t2]:
            if t in team_games: team_games[t] += 1
            if t in team_prox: team_prox[t].append(proximity)
        corrections.append({'jogo': int(r['jogo']), 'data': r['data'], 'fase': r['fase'], 'equipe1': t1, 'equipe2': t2, 'previsao_antes': f'{p1}-{p2}', 'resultado_real': f'{a1}-{a2}', 'vencedor_previsto': pred['vencedor_simulado'], 'vencedor_real': r['vencedor_real'], 'erro_gols_equipe1': a1-p1, 'erro_gols_equipe2': a2-p2, 'erro_total_gols': err_total, 'erro_saldo': err_saldo, 'acertou_vencedor': 'Sim' if outcome_ok else 'Não', 'acertou_placar_exato': 'Sim' if exact else 'Não', 'proximidade_0_100': proximity, 'ajuste_rating_equipe1': adj, 'ajuste_rating_equipe2': -adj, 'correcao_registrada': 'placar exato' if exact else ('vencedor correto, placar ajustado' if outcome_ok else 'vencedor corrigido'), 'arbitro_principal': pred.get('arbitro_principal',''), 'rigor_cartoes_simulado_0_10': pred.get('rigor_cartoes_simulado_0_10',''), 'fluidez_jogo_simulada_0_10': pred.get('fluidez_jogo_simulada_0_10','')})
    cor_df = pd.DataFrame(corrections).sort_values('jogo')
    actual_games = set(real_df['jogo'].astype(int))
    pred_rows = []
    for _, pred in sim.sort_values('jogo').iterrows():
        jogo = int(pred['jogo'])
        t1, t2 = str(pred['equipe1']), str(pred['equipe2'])
        p1, p2 = int(pred['gols1_sim']), int(pred['gols2_sim'])
        if jogo in actual_games:
            u1, u2 = p1, p2
            tipo = 'Previsão registrada antes do resultado'
        else:
            rel = rating_delta.get(t1,0) - rating_delta.get(t2,0)
            u1 = max(0, int(round(float(pred.get('xg1_modelo', p1)) + rel * 0.55)))
            u2 = max(0, int(round(float(pred.get('xg2_modelo', p2)) - rel * 0.55)))
            if u1 == 0 and u2 == 0 and (p1+p2) > 0:
                u1 = 1 if float(pred.get('xg1_modelo', p1)) >= float(pred.get('xg2_modelo', p2)) else 0
                u2 = 0 if u1 == 1 else 1
            tipo = 'Simulação atualizada pelo aprendizado'
        pred_rows.append({'jogo': jogo, 'fase': pred['fase'], 'grupo': pred.get('grupo',''), 'data': pred['data'], 'equipe1_prevista': t1, 'equipe2_prevista': t2, 'placar_previsto_original': pred['placar_simulado'], 'gols1_previsto_original': p1, 'gols2_previsto_original': p2, 'placar_previsto_atual': f'{u1}-{u2}', 'gols1_previsto_atual': u1, 'gols2_previsto_atual': u2, 'vencedor_previsto_original': pred['vencedor_simulado'], 'vencedor_previsto_atual': winner(t1,u1,t2,u2), 'tipo_previsao': tipo, 'confianca_modelo': pred.get('confianca_modelo',''), 'xg1_modelo': pred.get('xg1_modelo',''), 'xg2_modelo': pred.get('xg2_modelo',''), 'arbitro_principal': pred.get('arbitro_principal',''), 'rigor_cartoes_simulado_0_10': pred.get('rigor_cartoes_simulado_0_10',''), 'fluidez_jogo_simulada_0_10': pred.get('fluidez_jogo_simulada_0_10','')})
    pred_df = pd.DataFrame(pred_rows)
    team_state = []
    for team in sorted(team_strength):
        prox = team_prox.get(team, [])
        team_state.append({'selecao': team, 'forca_inicial_0_100': round(team_strength[team],2), 'ajuste_acumulado': round(rating_delta.get(team,0.0),3), 'forca_atualizada_0_100': round(team_strength[team]+rating_delta.get(team,0.0),2), 'jogos_corrigidos': team_games.get(team,0), 'proximidade_media_0_100': round(sum(prox)/len(prox),1) if prox else ''})
    team_state = pd.DataFrame(team_state)
    metrics = {'jogos_com_resultado_real': int(len(real_df)), 'jogos_com_correcao': int(len(cor_df)), 'proximidade_media_0_100': round(float(cor_df['proximidade_0_100'].mean()),1) if len(cor_df) else None, 'erro_medio_total_gols': round(float(cor_df['erro_total_gols'].mean()),2) if len(cor_df) else None, 'acuracia_vencedor_percentual': round(float((cor_df['acertou_vencedor']=='Sim').mean()*100),1) if len(cor_df) else None, 'placar_exato_percentual': round(float((cor_df['acertou_placar_exato']=='Sim').mean()*100),1) if len(cor_df) else None, 'ultima_entrada_real': str(real_df['data'].max()) if len(real_df) else None, 'learning_rate': learning_rate, 'logica': 'modelo incremental que compara previsão x real, registra erro e ajusta forças das seleções para os próximos jogos'}
    pred_df.to_csv(PRED_CSV, index=False, encoding='utf-8-sig')
    cor_df.to_csv(OUT_CORR, index=False, encoding='utf-8-sig')
    team_state.to_csv(OUT_STATE, index=False, encoding='utf-8-sig')
    OUT_JSON.write_text(json.dumps({'metrics': metrics, 'teams': team_state.to_dict(orient='records')}, ensure_ascii=False, indent=2), encoding='utf-8')
    js = 'window.WC2026_PREDICTIONS = ' + json.dumps(pred_df.to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_REAL_RESULTS = ' + json.dumps(real_df.to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_CORRECTIONS = ' + json.dumps(cor_df.to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_MODEL_METRICS = ' + json.dumps(metrics, ensure_ascii=False) + ';\n'
    OUT_JS.write_text(js, encoding='utf-8')
    with OUT_TXT.open('w', encoding='utf-8') as f:
        f.write('jogo;status;placar;equipe1;equipe2;vencedor\n')
        for _, r in real_df.sort_values('jogo').iterrows():
            f.write(f"{int(r['jogo'])};Finalizado;{r['placar_real']};{r['equipe1']};{r['equipe2']};{r['vencedor_real']}\n")

base = pd.DataFrame(parse_base()['matches'])
real_df = pd.read_csv(REAL_CSV, encoding='utf-8-sig') if REAL_CSV.exists() else pd.DataFrame()
new_df = load_new_results(base)
if not new_df.empty:
    real_df = pd.concat([real_df, new_df], ignore_index=True)
    real_df = real_df.sort_values('jogo').drop_duplicates('jogo', keep='last')
    real_df.to_csv(REAL_CSV, index=False, encoding='utf-8-sig')
    # clear template but keep header after processing
    pd.DataFrame(columns=['data','dia_semana','fase','time_1','gols_time_1','gols_time_2','time_2','placar','status','fonte']).to_csv(NEW_CSV, index=False, sep=';', encoding='utf-8-sig')
    print(f'{len(new_df)} nova(s) entrada(s) processada(s).')
else:
    print('Nenhuma nova entrada encontrada. Recalculando estado atual.')
rebuild(real_df)
subprocess.run([sys.executable, str(ROOT / 'scripts' / 'recalcular_mata_mata.py')], check=True)
subprocess.run([sys.executable, str(ROOT / 'scripts' / 'recalcular_modelo_contextual.py')], check=True)
print('Modelo, mata-mata, força contextual e visualizador atualizados.')
