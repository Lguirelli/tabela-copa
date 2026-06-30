(function () {
  const baseMatches = window.WC2026_DATA?.matches || [];
  const dailyPredictions = window.WC2026_MODELO_DIARIO_PREVISOES || [];
  const dailyMetrics = window.WC2026_MODELO_DIARIO_METRICAS || {};
  const neuralPredictions = window.WC2026_REDE_NEURAL_PREVISOES || [];
  const neuralMetrics = window.WC2026_REDE_NEURAL_METRICAS || {};

  const byGame = (rows) => new Map((rows || []).map((row) => [Number(row.jogo), row]));
  const dailyByGame = byGame(dailyPredictions);
  const neuralByGame = byGame(neuralPredictions);

  function parseScore(score) {
    const found = String(score || '').replace(/\s/g, '').match(/^(\d+)(?:-|x|:)(\d+)$/i);
    return found ? [Number(found[1]), Number(found[2])] : null;
  }

  function scoreWinner(team1, team2, score, fallback = 'Empate') {
    const parsed = parseScore(score);
    if (!parsed) return fallback || 'Empate';
    if (parsed[0] > parsed[1]) return team1;
    if (parsed[1] > parsed[0]) return team2;
    return 'Empate';
  }

  function value(...items) {
    return items.find((item) => item !== undefined && item !== null && String(item).trim() !== '') ?? '';
  }

  const activePredictions = baseMatches.map((base) => {
    const game = Number(base.jogo);
    const daily = dailyByGame.get(game) || {};
    const neural = neuralByGame.get(game) || {};
    const equipe1 = value(base.equipe1, daily.equipe1, neural.equipe1);
    const equipe2 = value(base.equipe2, daily.equipe2, neural.equipe2);
    const dailyScore = value(daily.placar_previsto);
    const neuralScore = value(neural.placar_rede_neural);
    const predictionScore = value(dailyScore, neuralScore);
    const dailyWinner = value(daily.vencedor_previsto);
    const neuralWinner = value(neural.vencedor_rede_neural);
    const predictionWinner = value(dailyWinner, neuralWinner, scoreWinner(equipe1, equipe2, predictionScore));
    const realScore = value(base.placar_real, neural.placar_real);
    const hasReal = Boolean(realScore) && (base.status === 'Finalizado' || neural.possui_real === 'Sim');
    const realWinner = hasReal ? value(base.vencedor_real, scoreWinner(equipe1, equipe2, realScore)) : '';
    const source = dailyScore ? 'Modelo diário' : (neuralScore ? 'Rede neural' : 'Sem previsão');

    return {
      ...neural,
      ...daily,
      jogo: game,
      data: value(base.data, daily.data, neural.data),
      fase: value(base.fase, daily.fase, neural.fase),
      grupo: value(base.grupo, daily.grupo, neural.grupo),
      rodadaGrupo: value(base.rodadaGrupo, daily.rodadaGrupo, neural.rodadaGrupo),
      equipe1,
      equipe2,
      confronto: `${equipe1} x ${equipe2}`,
      fonte_previsao: source,
      placar_previsto: predictionScore,
      vencedor_previsto: predictionWinner,
      placar_modelo_diario: dailyScore,
      vencedor_modelo_diario: dailyWinner,
      placar_rede_neural_original: neuralScore,
      vencedor_rede_neural_original: neuralWinner,
      placar_rede_neural: predictionScore,
      vencedor_rede_neural: predictionWinner,
      gols1_previsto: value(daily.gols1_previsto, neural.gols1_rede_neural),
      gols2_previsto: value(daily.gols2_previsto, neural.gols2_rede_neural),
      possui_real: hasReal ? 'Sim' : 'Não',
      placar_real: hasReal ? realScore : '',
      vencedor_real: realWinner,
      status_real: hasReal ? 'Finalizado' : '',
      usa_desempenho_copa: dailyScore ? 'Sim' : 'Não',
      explicacao_fonte: dailyScore
        ? 'Previsão ativa gerada pelo modelo diário incremental, com momentum e memória de desempenho acumulados durante a Copa.'
        : 'Fallback da rede neural pura quando não houver previsão diária.'
    };
  });

  window.WC2026_ACTIVE_PREVISOES = activePredictions;
  window.WC2026_ACTIVE_METRICAS = {
    ...neuralMetrics,
    ...dailyMetrics,
    modelo_ativo: 'Modelo diário incremental',
    modelo_secundario: neuralMetrics.modelo || 'Rede neural pura',
    fonte_previsao: 'data/modelo_diario/previsoes_dia_a_dia.csv',
    usa_desempenho_copa: true,
    usa_placar_real_quando_disponivel: true,
    observacao: 'O front prioriza placar real quando disponível. Para jogos sem real, prioriza o modelo diário incremental; a rede neural pura fica como referência secundária.'
  };
})();
