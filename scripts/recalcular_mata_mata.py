#!/usr/bin/env python3
"""
Recalcula o mata-mata a partir do estado atual do repositório.

Lógica:
- Fase de grupos: usa resultado real quando disponível e previsão quando ainda não há resultado.
- Mata-mata: usa vencedores reais quando disponíveis; quando não há resultado, simula pelo rating atualizado.
- Atualiza data/matches.csv, data/matches.json, data/previsoes_modelo.csv, data/database/simulated_matches.csv, src/data.js e src/model-data.js.
"""
from pathlib import Path
import json, re, unicodedata
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

ALIASES_NORM = {
    'holanda paises baixos': 'paises baixos', 'holanda': 'paises baixos', 'paises baixos': 'paises baixos',
    'rd congo': 'rd congo', 'rd do congo': 'rd congo', 'republica democratica do congo': 'rd congo', 'congo kinshasa': 'rd congo', 'congo dr': 'rd congo', 'dr congo': 'rd congo',
    'republica da coreia': 'coreia do sul', 'korea republic': 'coreia do sul', 'coreia republica': 'coreia do sul',
    'republica tcheca': 'tchequia', 'tchequia': 'tchequia',
    'eua': 'estados unidos', 'usa': 'estados unidos', 'turkiye': 'turquia',
    'ir iran': 'ira', 'iran': 'ira', 'ivory coast': 'costa do marfim'
}

def norm(value):
    value = str(value or '').strip().lower()
    value = unicodedata.normalize('NFD', value)
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    value = re.sub(r'[^a-z0-9 ]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    return ALIASES_NORM.get(value, value)

def parse_score(score):
    m = re.match(r'\s*(\d+)\D+(\d+)', str(score or ''))
    return (int(m.group(1)), int(m.group(2))) if m else None

def score_winner(t1, g1, t2, g2):
    if int(g1) > int(g2):
        return t1
    if int(g2) > int(g1):
        return t2
    return 'Empate'

def read_csv(path):
    return pd.read_csv(path, encoding='utf-8-sig') if path.exists() else pd.DataFrame()

def get_real_winner(real_row):
    winner = str(real_row.get('vencedor_real', '')).strip()
    if winner and winner != 'Empate':
        return winner
    t1, t2 = str(real_row.get('equipe1')), str(real_row.get('equipe2'))
    g1, g2 = int(real_row.get('gols1_real', 0)), int(real_row.get('gols2_real', 0))
    return score_winner(t1, g1, t2, g2)

def main():
    matches = read_csv(ROOT / 'data/matches.csv')
    pred = read_csv(ROOT / 'data/previsoes_modelo.csv')
    real = read_csv(ROOT / 'data/resultados_reais.csv')
    corrections = read_csv(ROOT / 'data/neural/correcoes_modelo.csv')
    state = read_csv(ROOT / 'data/neural/estado_times.csv')
    team_strengths = read_csv(ROOT / 'data/database/team_strengths.csv')
    sim = read_csv(ROOT / 'data/database/simulated_matches.csv')

    if matches.empty or pred.empty:
        raise SystemExit('Arquivos base ausentes: data/matches.csv ou data/previsoes_modelo.csv')

    pred_by_game = {int(r.jogo): r for r in pred.itertuples()}
    real_by_game = {int(r.jogo): r for r in real.itertuples()} if not real.empty else {}

    group_order, groups = [], {}
    for _, r in matches[matches['fase'] == 'Fase de grupos'].iterrows():
        g = str(r['grupo'])
        if g not in groups:
            groups[g] = []
            group_order.append(g)
        for t in [r['equipe1'], r['equipe2']]:
            if t not in groups[g]:
                groups[g].append(t)

    standings = {}
    for g in group_order:
        table = {t: {'grupo': g, 'team': t, 'pts': 0, 'j': 0, 'v': 0, 'e': 0, 'd': 0, 'gf': 0, 'ga': 0} for t in groups[g]}
        for _, row in matches[(matches['fase'] == 'Fase de grupos') & (matches['grupo'].astype(str) == g)].iterrows():
            jogo = int(row['jogo'])
            if jogo in real_by_game:
                rr = real_by_game[jogo]
                t1, t2 = str(rr.equipe1), str(rr.equipe2)
                score = (int(rr.gols1_real), int(rr.gols2_real))
            else:
                pp = pred_by_game.get(jogo)
                if pp is None:
                    continue
                t1, t2 = str(pp.equipe1_prevista), str(pp.equipe2_prevista)
                score = parse_score(pp.placar_previsto_atual) or parse_score(pp.placar_previsto_original)
            if not score or t1 not in table or t2 not in table:
                continue
            g1, g2 = score
            for t in [t1, t2]:
                table[t]['j'] += 1
            table[t1]['gf'] += g1; table[t1]['ga'] += g2
            table[t2]['gf'] += g2; table[t2]['ga'] += g1
            if g1 > g2:
                table[t1]['v'] += 1; table[t2]['d'] += 1; table[t1]['pts'] += 3
            elif g2 > g1:
                table[t2]['v'] += 1; table[t1]['d'] += 1; table[t2]['pts'] += 3
            else:
                table[t1]['e'] += 1; table[t2]['e'] += 1; table[t1]['pts'] += 1; table[t2]['pts'] += 1
        rows = []
        for vals in table.values():
            vals['gd'] = vals['gf'] - vals['ga']
            rows.append(vals)
        rows = sorted(rows, key=lambda x: (-x['pts'], -x['gd'], -x['gf'], x['team']))
        for i, r in enumerate(rows, 1):
            r['posicao'] = i
        standings[g] = rows

    stand_rows = [row for g in group_order for row in standings[g]]
    pd.DataFrame(stand_rows).to_csv(ROOT / 'data/neural/classificacao_projetada_grupos.csv', index=False, encoding='utf-8-sig')

    def rank_team(group, pos):
        return standings[group][pos - 1]['team']

    thirds = [{**standings[g][2], 'group': g} for g in group_order]
    thirds = sorted(thirds, key=lambda x: (-x['pts'], -x['gd'], -x['gf'], x['team']))
    best_thirds = thirds[:8]
    best_groups = [x['group'] for x in best_thirds]
    best_team = {x['group']: x['team'] for x in best_thirds}

    third_slots = {
        74: list('ABCDF'), 77: list('CDFGH'), 79: list('CEFHI'), 80: list('EHIJK'),
        81: list('BEFIJ'), 82: list('AEHIJ'), 85: list('EFGIJ'), 87: list('DEIJL')
    }
    forced = {81: 'B'} if 'B' in best_groups else {}
    rank_idx = {g: i for i, g in enumerate(best_groups)}

    def backtrack(assign, remaining, slots_left):
        if not slots_left:
            return [assign]
        s = min(slots_left, key=lambda x: len([g for g in remaining if g in third_slots[x]]))
        sols = []
        for g in sorted([g for g in remaining if g in third_slots[s]], key=lambda x: rank_idx.get(x, 999)):
            sols += backtrack({**assign, s: g}, [r for r in remaining if r != g], [x for x in slots_left if x != s])
        return sols

    remaining = [g for g in best_groups if g not in forced.values()]
    slots_left = [s for s in third_slots if s not in forced]
    sols = backtrack(dict(forced), remaining, slots_left)
    assignment = min(sols, key=lambda a: sum(rank_idx.get(a[s], 99) * i for i, s in enumerate(sorted(a)))) if sols else {}

    r32 = {
        73: (rank_team('A', 2), rank_team('B', 2)),
        74: (rank_team('E', 1), best_team.get(assignment.get(74), '3º Grupo A/B/C/D/F')),
        75: (rank_team('F', 1), rank_team('C', 2)),
        76: (rank_team('C', 1), rank_team('F', 2)),
        77: (rank_team('I', 1), best_team.get(assignment.get(77), '3º Grupo C/D/F/G/H')),
        78: (rank_team('E', 2), rank_team('I', 2)),
        79: (rank_team('A', 1), best_team.get(assignment.get(79), '3º Grupo C/E/F/H/I')),
        80: (rank_team('L', 1), best_team.get(assignment.get(80), '3º Grupo E/H/I/J/K')),
        81: (rank_team('D', 1), best_team.get(assignment.get(81), '3º Grupo B/E/F/I/J')),
        82: (rank_team('G', 1), best_team.get(assignment.get(82), '3º Grupo A/E/H/I/J')),
        83: (rank_team('K', 2), rank_team('L', 2)),
        84: (rank_team('H', 1), rank_team('J', 2)),
        85: (rank_team('B', 1), best_team.get(assignment.get(85), '3º Grupo E/F/G/I/J')),
        86: (rank_team('J', 1), rank_team('H', 2)),
        87: (rank_team('K', 1), best_team.get(assignment.get(87), '3º Grupo D/E/I/J/L')),
        88: (rank_team('D', 2), rank_team('G', 2)),
    }

    def get_strength(team):
        row = state[state['selecao'].apply(norm) == norm(team)] if not state.empty else pd.DataFrame()
        if not row.empty:
            return float(row.iloc[0]['forca_atualizada_0_100'])
        row = team_strengths[team_strengths['selecao'].apply(norm) == norm(team)] if not team_strengths.empty else pd.DataFrame()
        if not row.empty:
            return float(row.iloc[0]['forca_modelo_0_100'])
        return 60.0

    info_map = {norm(r['selecao']): r for _, r in team_strengths.iterrows()} if not team_strengths.empty else {}
    def info(team, field, default=''):
        return info_map.get(norm(team), {}).get(field, default)
    def simulate(t1, t2):
        s1, s2 = get_strength(t1), get_strength(t2)
        diff = s1 - s2
        if abs(diff) < 0.85:
            winner = t1 if diff >= 0 else t2
            return '1-1 (p)', 1, 1, winner, 'Sim'
        if diff > 0:
            winner = t1
            score = (3, 0) if diff >= 7 else (2, 0) if diff >= 3.2 else (2, 1)
        else:
            winner = t2
            diff = abs(diff)
            score = (0, 3) if diff >= 7 else (0, 2) if diff >= 3.2 else (1, 2)
        return f'{score[0]}-{score[1]}', score[0], score[1], winner, 'Não'

    pairs, winners, losers = {}, {}, {}
    for j in range(73, 89):
        pair = r32[j]
        if j in real_by_game:
            rr = real_by_game[j]
            pair = (str(rr.equipe1), str(rr.equipe2))
            win = get_real_winner(pd.Series(rr._asdict()))
        else:
            _, _, _, win, _ = simulate(*pair)
        pairs[j] = pair
        winners[j] = win
        losers[j] = pair[1] if win == pair[0] else pair[0]

    next_map = {
        89: (73, 75), 90: (74, 77), 91: (76, 78), 92: (79, 80),
        93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
        97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
        101: (97, 98), 102: (99, 100), 104: (101, 102)
    }
    for j, (a, b) in next_map.items():
        pair = (winners[a], winners[b])
        if j in real_by_game:
            rr = real_by_game[j]
            pair = (str(rr.equipe1), str(rr.equipe2))
            win = get_real_winner(pd.Series(rr._asdict()))
        else:
            _, _, _, win, _ = simulate(*pair)
        pairs[j] = pair
        winners[j] = win
        losers[j] = pair[1] if win == pair[0] else pair[0]

    pairs[103] = (losers[101], losers[102])
    if 103 in real_by_game:
        rr = real_by_game[103]
        pairs[103] = (str(rr.equipe1), str(rr.equipe2))
        winners[103] = get_real_winner(pd.Series(rr._asdict()))
    else:
        _, _, _, winners[103], _ = simulate(*pairs[103])
    losers[103] = pairs[103][1] if winners[103] == pairs[103][0] else pairs[103][0]

    for idx, r in pred[pred['jogo'].astype(int).isin(pairs.keys())].iterrows():
        j = int(r['jogo'])
        t1, t2 = pairs[j]
        score, g1, g2, win, pens = simulate(t1, t2)
        pred.loc[idx, ['equipe1_prevista', 'equipe2_prevista', 'placar_previsto_original', 'gols1_previsto_original', 'gols2_previsto_original', 'placar_previsto_atual', 'gols1_previsto_atual', 'gols2_previsto_atual', 'vencedor_previsto_original', 'vencedor_previsto_atual']] = [t1, t2, score, g1, g2, score, g1, g2, win, win]
        pred.at[idx, 'tipo_previsao'] = 'Mata-mata recalculado pela classificação atual + aprendizado'
        pred.at[idx, 'xg1_modelo'] = round(max(0.6, 1.15 + (get_strength(t1) - get_strength(t2)) * 0.035), 2)
        pred.at[idx, 'xg2_modelo'] = round(max(0.6, 1.15 + (get_strength(t2) - get_strength(t1)) * 0.035), 2)
        pred.at[idx, 'confianca_modelo'] = 'alta' if abs(get_strength(t1) - get_strength(t2)) >= 5 else 'média' if abs(get_strength(t1) - get_strength(t2)) >= 2 else 'baixa'

    for idx, r in matches[matches['jogo'].astype(int).isin(pairs.keys())].iterrows():
        j = int(r['jogo'])
        t1, t2 = pairs[j]
        matches.at[idx, 'equipe1'] = t1
        matches.at[idx, 'equipe2'] = t2
        matches.at[idx, 'confronto'] = f'{t1} x {t2}'
        matches.at[idx, 'status'] = 'Finalizado' if j in real_by_game else 'Simulação'

    if not sim.empty:
        for idx, r in sim[sim['jogo'].astype(int).isin(pairs.keys())].iterrows():
            j = int(r['jogo'])
            t1, t2 = pairs[j]
            score, g1, g2, win, pens = simulate(t1, t2)
            sim.at[idx, 'equipe1'] = t1; sim.at[idx, 'equipe2'] = t2
            sim.at[idx, 'codigo1'] = info(t1, 'codigo', '')
            sim.at[idx, 'codigo2'] = info(t2, 'codigo', '')
            sim.at[idx, 'placar_simulado'] = score
            sim.at[idx, 'gols1_sim'] = g1; sim.at[idx, 'gols2_sim'] = g2
            sim.at[idx, 'xg1_modelo'] = round(max(0.6, 1.15 + (get_strength(t1) - get_strength(t2)) * 0.035), 2)
            sim.at[idx, 'xg2_modelo'] = round(max(0.6, 1.15 + (get_strength(t2) - get_strength(t1)) * 0.035), 2)
            sim.at[idx, 'vencedor_simulado'] = win
            sim.at[idx, 'decidido_penaltis'] = pens
            sim.at[idx, 'forca_equipe1'] = round(get_strength(t1), 2)
            sim.at[idx, 'forca_equipe2'] = round(get_strength(t2), 2)
            sim.at[idx, 'estilo_equipe1'] = info(t1, 'estilo_tecnico', '')
            sim.at[idx, 'estilo_equipe2'] = info(t2, 'estilo_tecnico', '')
            sim.at[idx, 'tecnico_equipe1'] = info(t1, 'tecnico', '')
            sim.at[idx, 'tecnico_equipe2'] = info(t2, 'tecnico', '')
            sim.at[idx, 'confianca_modelo'] = 'alta' if abs(get_strength(t1) - get_strength(t2)) >= 5 else 'média' if abs(get_strength(t1) - get_strength(t2)) >= 2 else 'baixa'

    pd.DataFrame(best_thirds).to_csv(ROOT / 'data/neural/melhores_terceiros_projetados.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame([{
        'jogo': j, 'slot_original': '/'.join(third_slots[j]), 'grupo_terceiro_usado': assignment.get(j, ''), 'selecao_terceira_usada': best_team.get(assignment.get(j, ''), '')
    } for j in sorted(third_slots)]).to_csv(ROOT / 'data/neural/terceiros_colocados_mata_mata.csv', index=False, encoding='utf-8-sig')

    report = {'r32': {str(j): {'equipe1': pairs[j][0], 'equipe2': pairs[j][1], 'vencedor_previsto': winners[j]} for j in range(73, 89)}, 'champion_projected': winners.get(104)}
    (ROOT / 'data/neural/debug_mata_mata_atualizado.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    matches.to_csv(ROOT / 'data/matches.csv', index=False, encoding='utf-8-sig')
    pred.to_csv(ROOT / 'data/previsoes_modelo.csv', index=False, encoding='utf-8-sig')
    if not sim.empty:
        sim.to_csv(ROOT / 'data/database/simulated_matches.csv', index=False, encoding='utf-8-sig')

    matches_json = matches.where(pd.notna(matches), None).to_dict(orient='records')
    groups_json = [{'grupo': g, 'equipes': groups[g]} for g in group_order]
    summary = {
        'totalJogos': int(len(matches)),
        'faseGrupos': int((matches['fase'] == 'Fase de grupos').sum()),
        'mataMata': int((matches['fase'] != 'Fase de grupos').sum()),
        'grupos': len(group_order),
        'selecoes': sum(len(v) for v in groups.values()),
        'periodo': f"{matches['data'].min()} a {matches['data'].max()}"
    }
    (ROOT / 'data/matches.json').write_text(json.dumps(matches_json, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'src/data.js').write_text('window.WC2026_DATA = ' + json.dumps({'summary': summary, 'groups': groups_json, 'matches': matches_json}, ensure_ascii=False, indent=2) + ';\n', encoding='utf-8')

    metrics_path = ROOT / 'data/neural/model_state.json'
    metrics = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding='utf-8')).get('metrics', {})
        except Exception:
            metrics = {}
    if not metrics:
        metrics = {'jogos_com_resultado_real': int(len(real)), 'jogos_com_correcao': int(len(corrections))}

    js = 'window.WC2026_PREDICTIONS = ' + json.dumps(pred.where(pd.notna(pred), '').to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_REAL_RESULTS = ' + json.dumps(real.where(pd.notna(real), '').to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_CORRECTIONS = ' + json.dumps(corrections.where(pd.notna(corrections), '').to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_MODEL_METRICS = ' + json.dumps(metrics, ensure_ascii=False) + ';\n'
    (ROOT / 'src/model-data.js').write_text(js, encoding='utf-8')
    print('Mata-mata recalculado com a classificação atual.')

if __name__ == '__main__':
    main()
