from pathlib import Path
import json
import math
import re
import unicodedata
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'data' / 'modelo'
OUT_DIR.mkdir(parents=True, exist_ok=True)

league_weights = {
    'ENG': 10.0, 'ESP': 9.8, 'GER': 9.5, 'DEU': 9.5, 'ITA': 9.4, 'FRA': 9.0,
    'POR': 8.5, 'NED': 8.4, 'BEL': 8.0, 'TUR': 8.0, 'BRA': 8.2, 'ARG': 8.1,
    'USA': 7.4, 'MEX': 7.3, 'KSA': 7.2, 'QAT': 6.9, 'SCO': 7.3, 'CHE': 7.6,
    'AUT': 7.5, 'NOR': 7.2, 'SWE': 7.1, 'CZE': 6.9, 'JPN': 6.9, 'KOR': 6.8,
    'COL': 6.8, 'ECU': 6.7, 'URU': 6.8, 'PAR': 6.5, 'IRN': 6.2, 'IRQ': 5.8,
    'AUS': 6.4, 'CAN': 6.4, 'MAR': 6.4, 'EGY': 6.2, 'RSA': 6.1, 'DZA': 6.1,
    'SEN': 6.1, 'CIV': 6.1, 'GHA': 6.1, 'BIH': 6.2, 'TUN': 6.0, 'CPV': 5.8,
    'COD': 5.8, 'UZB': 5.7, 'PAN': 5.7, 'NZL': 5.7, 'JOR': 5.5, 'HTI': 5.4,
    'CUW': 5.4
}

def norm(value):
    value = unicodedata.normalize('NFD', str(value or ''))
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()

def mention_score(row):
    text = norm(str(row.get('Tipo de desempenho','')) + ' ' + str(row.get('Detalhe pesquisado','')))
    score = 1.0
    if any(x in text for x in ['2 gols','gol destaque','gol decisivo','mvp','destaque','assistencia','lideranca']):
        score += 0.6
    if any(x in text for x in ['baixo','abaixo','negativa','expuls','erro','falha']):
        score -= 1.3
    if any(x in text for x in ['clean sheet','goleiro','defesa']):
        score += 0.3
    return score

def main():
    players = pd.read_csv(ROOT / 'data/database/players_database.csv')
    strength = pd.read_csv(ROOT / 'data/database/team_strengths.csv')
    real = pd.read_csv(ROOT / 'data/resultados_reais.csv') if (ROOT / 'data/resultados_reais.csv').exists() else pd.DataFrame()
    state = pd.read_csv(ROOT / 'data/neural/estado_times.csv') if (ROOT / 'data/neural/estado_times.csv').exists() else pd.DataFrame()

    alias = {}
    for _, r in strength.iterrows():
        alias[norm(r['selecao'])] = r['selecao']
        if 'selecao_xlsx' in r:
            alias[norm(r['selecao_xlsx'])] = r['selecao']
    alias.update({norm(k): v for k, v in {
        'Algeria':'Argélia','Korea Republic':'Coreia do Sul','South Korea':'Coreia do Sul','Czechia':'Tchéquia',
        'Czech Republic':'Tchéquia','Netherlands':'Países Baixos','Ivory Coast':'Costa do Marfim','Turkey':'Turquia',
        'Turkiye':'Turquia','United States':'Estados Unidos','DR Congo':'RD Congo','Congo DR':'RD Congo',
        'Uzbekistan':'Uzbequistão','Saudi Arabia':'Arábia Saudita','Cape Verde':'Cabo Verde',
        'New Zealand':'Nova Zelândia','South Africa':'África do Sul','Morocco':'Marrocos'
    }.items()})

    def team(value):
        return alias.get(norm(value), str(value))

    players['selecao'] = players['Seleção'].map(team)
    players['league_weight'] = players['País do clube'].fillna('').map(lambda x: league_weights.get(str(x).upper().strip(), 6.2))
    players['proxy'] = pd.to_numeric(players['Índice proxy 0-10'], errors='coerce').fillna(5.0)
    players['caps'] = pd.to_numeric(players['Caps seleção'], errors='coerce').fillna(0)
    players['goals'] = pd.to_numeric(players['Gols seleção'], errors='coerce').fillna(0)
    players['player_weight'] = players['proxy']*.50 + players['league_weight']*.32 + (players['caps'].clip(0,100)/100*10)*.12 + (players['goals'].clip(0,40)/40*10)*.06

    team_player = players.groupby('selecao').agg(
        jogadores=('Jogador','count'),
        liga_media=('league_weight','mean'),
        liga_top11=('league_weight', lambda s: s.sort_values(ascending=False).head(11).mean()),
        desempenho_proxy_medio=('proxy','mean'),
        desempenho_top18=('player_weight', lambda s: s.sort_values(ascending=False).head(18).mean())
    ).reset_index()

    perf_path = ROOT / 'data/desempenho/jogadores_citados_desempenho_copa_2026.csv'
    if perf_path.exists():
        perf = pd.read_csv(perf_path, sep=';', encoding='utf-8-sig')
        perf['selecao'] = perf['Seleção'].map(team)
        perf['impacto'] = perf.apply(mention_score, axis=1)
        perf_team = perf.groupby('selecao').agg(citacoes_jogadores=('Jogador','count'), impacto_jogadores_copa=('impacto','sum')).reset_index()
    else:
        perf_team = pd.DataFrame(columns=['selecao','citacoes_jogadores','impacto_jogadores_copa'])

    if not real.empty:
        real['data_dt'] = pd.to_datetime(real['data'], errors='coerce')
        latest = real['data_dt'].max()
        rows = []
        for _, r in real.iterrows():
            if pd.isna(r['data_dt']): continue
            days = max(0, (latest - r['data_dt']).days)
            decay = math.exp(-days/10)
            g1, g2 = int(r['gols1_real']), int(r['gols2_real'])
            rows.append({'selecao': team(r['equipe1']), 'impacto_resultado_anterior': (g1-g2)*decay, 'jogo': r['jogo']})
            rows.append({'selecao': team(r['equipe2']), 'impacto_resultado_anterior': (g2-g1)*decay, 'jogo': r['jogo']})
        momentum = pd.DataFrame(rows).groupby('selecao').agg(jogos_reais=('jogo','count'), impacto_resultado_anterior=('impacto_resultado_anterior','sum')).reset_index()
    else:
        momentum = pd.DataFrame(columns=['selecao','jogos_reais','impacto_resultado_anterior'])

    model = strength[['selecao','grupo','codigo','tecnico','estilo_tecnico','sistema_base','forca_modelo_0_100']].copy()
    for df in [team_player, perf_team, momentum]:
        model = model.merge(df, on='selecao', how='left')
    if not state.empty:
        model = model.merge(state[['selecao','ajuste_acumulado']], on='selecao', how='left')
    for col in ['liga_media','liga_top11','desempenho_proxy_medio','desempenho_top18','citacoes_jogadores','impacto_jogadores_copa','impacto_resultado_anterior','ajuste_acumulado']:
        model[col] = pd.to_numeric(model[col], errors='coerce').fillna(0)
    model['competitividade_liga_0_100'] = (model['liga_top11'] * 10).round(1)
    model['desempenho_jogadores_0_100'] = (model['desempenho_top18'] * 10).round(1)
    model['momentum_data_0_100'] = (50 + model['impacto_resultado_anterior'] * 6).clip(0,100).round(1)
    model['ajuste_aprendizado_0_100'] = (50 + model['ajuste_acumulado'] * 5).clip(0,100).round(1)
    model['forca_contextual_0_100'] = (
        model['forca_modelo_0_100']*.42 + model['competitividade_liga_0_100']*.20 +
        model['desempenho_jogadores_0_100']*.18 + model['momentum_data_0_100']*.12 +
        model['ajuste_aprendizado_0_100']*.08
    ).round(1)
    model['explicacao_peso'] = 'base 42%, campeonato 20%, jogadores 18%, data/momentum 12%, correção 8%'
    model = model.sort_values('forca_contextual_0_100', ascending=False)
    model.to_csv(OUT_DIR / 'modelo_times.csv', index=False, encoding='utf-8-sig')

    matrix = pd.DataFrame([
        ['Competitividade do campeonato dos jogadores','forca_contextual_0_100','Quanto mais atletas em ligas fortes, maior a confiança no nível competitivo do elenco','20%','players_database.csv'],
        ['Desempenho dos jogadores','forca_contextual_0_100','Proxy individual e destaques reais ajustam a força do time','18%','players_database.csv + desempenho'],
        ['Força base do elenco','forca_contextual_0_100','Estrutura anterior por elenco, setores, caps e técnico','42%','team_strengths.csv'],
        ['Resultado anterior por data','momentum_data_0_100','Resultados recentes interferem mais na próxima previsão','12%','resultados_reais.csv'],
        ['Correção do modelo','ajuste_aprendizado_0_100','Erro registrado ajusta rating acumulado','8%','correcoes_modelo.csv'],
    ], columns=['variavel','influencia','como_interpreta','peso_modelo','fonte_base'])
    matrix.to_csv(OUT_DIR / 'matriz_variaveis.csv', index=False, encoding='utf-8-sig')

    js = 'window.WC2026_MODELO_TIMES = ' + json.dumps(model.fillna('').to_dict(orient='records'), ensure_ascii=False) + ';\n'
    js += 'window.WC2026_MATRIZ_VARIAVEIS = ' + json.dumps(matrix.to_dict(orient='records'), ensure_ascii=False) + ';\n'
    (ROOT / 'src/modelo-dados.js').write_text(js, encoding='utf-8')
    print('Modelo contextual recalculado com campeonato, desempenho, data/momentum e correções.')

if __name__ == '__main__':
    main()
