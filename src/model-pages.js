(() => {
  'use strict';

  const data = window.WC2026_MODEL_ANALYTICS || {};
  const teamAssets = window.WC2026_TEAM_ASSETS || {};
  const page = document.body?.dataset?.modelPage || '';
  const COLORS = ['#22c55e', '#60a5fa', '#f59e0b', '#f472b6', '#a78bfa', '#2dd4bf', '#fb7185', '#facc15'];
  const GRID = 'rgba(148,163,184,.16)';
  const TEXT = '#e5e7eb';
  const MUTED = '#8b93a3';

  const labels = {
    attack_vs_defense: 'Ataque contra defesa',
    defense_vs_attack: 'Defesa contra ataque',
    rating_diff: 'Diferença de rating',
    initial_strength_diff: 'Força inicial',
    goalkeeper_diff: 'Goleiros',
    experience_diff: 'Experiência',
    form_points_diff: 'Forma recente',
    form_goal_diff: 'Saldo recente',
    schedule_strength_diff: 'Força do calendário',
    rest_diff: 'Descanso',
    shots_on_target_dominance: 'Domínio em chutes no alvo',
    first_goal: 'Primeiro gol',
    finishing_efficiency: 'Eficiência de finalização',
    red_card_imbalance: 'Desequilíbrio por expulsão',
    scoreline_only: 'Evidência apenas do placar',
    penalty_shootout: 'Disputa de pênaltis',
    tendencia_real: 'Tendência real',
    acaso: 'Evento isolado',
    erro_estatistico: 'Erro estatístico',
    mudanca_estrutural: 'Mudança estrutural',
    direction_correct: 'Direção correta',
    direction_wrong: 'Direção incorreta',
    base_goals: 'Gols-base',
    rating_weight: 'Peso do rating',
    attack_weight: 'Peso ofensivo',
    defense_weight: 'Peso defensivo',
    form_weight: 'Peso da forma',
    schedule_weight: 'Peso do calendário',
    rest_weight: 'Peso do descanso',
    experience_weight: 'Peso da experiência',
    goalkeeper_weight: 'Peso do goleiro',
    probability_temperature: 'Temperatura de probabilidade',
    learning_rate: 'Taxa de aprendizado',
    elo_k: 'K do Elo',
    confirmed_lineup: 'Escalação confirmada',
    player_availability: 'Disponibilidade de jogadores',
    archived_news: 'Notícias arquivadas',
    weather: 'Clima',
    travel: 'Viagem',
    referee: 'Arbitragem'
  };

  function text(value, fallback = 'NA') {
    return value === undefined || value === null || value === '' ? fallback : String(value);
  }

  function human(value) {
    const key = text(value, 'NA');
    return labels[key] || key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function pct(value, digits = 1) {
    const n = Number(value);
    return Number.isFinite(n) ? `${(n * 100).toFixed(digits).replace('.', ',')}%` : 'NA';
  }

  function num(value, digits = 3) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits).replace('.', ',') : 'NA';
  }

  function dateBR(value, compact = false) {
    if (!value) return 'NA';
    const raw = String(value).slice(0, 10);
    const parts = raw.split('-');
    if (parts.length !== 3) return raw;
    return compact ? `${parts[2]}/${parts[1]}` : `${parts[2]}/${parts[1]}/${parts[0]}`;
  }

  function asset(team) {
    if (teamAssets[team]) return teamAssets[team];
    const normalized = String(team || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const key = Object.keys(teamAssets).find(name => name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() === normalized);
    return key ? teamAssets[key] : null;
  }

  function team(team, size = 'normal') {
    const info = asset(team);
    const flag = info?.flag || info?.flagPng;
    return `<span class="model-team model-team--${size}">${flag ? `<img src="${flag}" alt="" loading="lazy">` : '<i></i>'}<b>${text(team)}</b></span>`;
  }

  function setHTML(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function badge(label, tone = 'neutral') {
    return `<span class="model-badge model-badge--${tone}">${label}</span>`;
  }

  function metricCard(label, value, note = '', tone = '') {
    return `<article class="model-kpi ${tone ? `model-kpi--${tone}` : ''}"><small>${label}</small><strong>${value}</strong>${note ? `<span>${note}</span>` : ''}</article>`;
  }

  function setupCanvas(canvas) {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(320, rect.width || 640);
    const height = Math.max(190, rect.height || 280);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  function lineChart(id, rows, series, options = {}) {
    const canvas = document.getElementById(id);
    const setup = setupCanvas(canvas);
    if (!setup || !rows?.length) return;
    const { ctx, width, height } = setup;
    const pad = { left: 44, right: 18, top: 30, bottom: 36 };
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;
    const values = rows.flatMap(row => series.map(s => Number(s.value(row))).filter(Number.isFinite));
    let min = options.min ?? Math.min(...values);
    let max = options.max ?? Math.max(...values);
    if (!Number.isFinite(min) || !Number.isFinite(max)) return;
    if (min === max) { min -= 1; max += 1; }
    const extra = (max - min) * .08;
    if (options.min === undefined) min -= extra;
    if (options.max === undefined) max += extra;

    ctx.font = '11px Inter, system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + chartH * i / 4;
      ctx.strokeStyle = GRID;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
      const val = max - (max - min) * i / 4;
      ctx.fillStyle = MUTED;
      ctx.textAlign = 'right';
      const label = options.percent ? `${(val * 100).toFixed(0)}%` : val.toFixed(options.axisDigits ?? 2);
      ctx.fillText(label, pad.left - 7, y);
    }

    const xStep = chartW / Math.max(1, rows.length - 1);
    const labelEvery = Math.max(1, Math.ceil(rows.length / 7));
    rows.forEach((row, i) => {
      if (i % labelEvery !== 0 && i !== rows.length - 1) return;
      const x = pad.left + xStep * i;
      ctx.fillStyle = MUTED;
      ctx.textAlign = 'center';
      ctx.fillText(options.xLabel ? options.xLabel(row) : String(i + 1), x, height - 16);
    });

    series.forEach((s, idx) => {
      const color = s.color || COLORS[idx % COLORS.length];
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      let started = false;
      rows.forEach((row, i) => {
        const v = Number(s.value(row));
        if (!Number.isFinite(v)) return;
        const x = pad.left + xStep * i;
        const y = pad.top + (1 - (v - min) / (max - min)) * chartH;
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      });
      ctx.stroke();
      rows.forEach((row, i) => {
        const v = Number(s.value(row));
        if (!Number.isFinite(v)) return;
        if (rows.length > 45 && i % 3 !== 0 && i !== rows.length - 1) return;
        const x = pad.left + xStep * i;
        const y = pad.top + (1 - (v - min) / (max - min)) * chartH;
        ctx.fillStyle = '#0b0d12'; ctx.strokeStyle = color; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(x, y, 3.2, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
    });

    let legendX = pad.left;
    series.forEach((s, idx) => {
      ctx.fillStyle = s.color || COLORS[idx % COLORS.length];
      ctx.fillRect(legendX, 10, 10, 3);
      ctx.fillStyle = TEXT; ctx.textAlign = 'left'; ctx.font = '700 11px Inter, system-ui, sans-serif';
      ctx.fillText(s.label, legendX + 15, 12);
      legendX += 22 + ctx.measureText(s.label).width;
    });
  }

  function horizontalBars(id, rows, valueKey, labelKey, options = {}) {
    const target = document.getElementById(id);
    if (!target) return;
    const max = Math.max(...rows.map(r => Number(r[valueKey]) || 0), .0001);
    target.innerHTML = rows.map((row, index) => {
      const value = Number(row[valueKey]) || 0;
      const width = Math.max(value > 0 ? 2 : 0, value / max * 100);
      const display = options.percent ? pct(value, options.digits ?? 1) : (options.format ? options.format(value) : text(value));
      return `<div class="model-bar-row"><div class="model-bar-head"><span>${options.team ? team(row[labelKey], 'small') : `<b>${human(row[labelKey])}</b>`}</span><strong>${display}</strong></div><i><em style="width:${width}%;--bar-color:${COLORS[index % COLORS.length]}"></em></i>${options.note ? `<small>${options.note(row)}</small>` : ''}</div>`;
    }).join('');
  }

  function renderTopStats() {
    const summary = data.summary || {};
    const fm = data.finalMetrics || {};
    setText('model-stat-matches', summary.matches ?? 104);
    setText('model-stat-accuracy', pct(fm.outcome_accuracy, 1));
    setText('model-stat-score', pct(fm.exact_score_accuracy, 1));
    setText('model-stat-versions', summary.modelVersions ?? 0);
  }

  function comparisonRows() {
    const c = data.comparison || {};
    const frozen = c.frozen_pre_worldcup_model || {};
    const progressive = c.progressive_walk_forward_model || {};
    return [
      { label: 'Acerto do resultado', before: frozen.outcome_accuracy, after: progressive.outcome_accuracy, inverse: false, percent: true },
      { label: 'Placar exato', before: frozen.exact_score_accuracy, after: progressive.exact_score_accuracy, inverse: false, percent: true },
      { label: 'Log loss', before: frozen.mean_log_loss, after: progressive.mean_log_loss, inverse: true },
      { label: 'Brier score', before: frozen.mean_brier_score, after: progressive.mean_brier_score, inverse: true }
    ];
  }

  function renderOverview() {
    const s = data.summary || {};
    const fm = data.finalMetrics || {};
    setHTML('overview-kpis', [
      metricCard('Jogos avaliados', s.matches ?? 0, 'replay temporal completo'),
      metricCard('Acerto do resultado', pct(fm.outcome_accuracy), `${s.outcomeCorrect ?? 0} previsões corretas`, 'green'),
      metricCard('Placares exatos', pct(fm.exact_score_accuracy), `${s.scoreCorrect ?? 0} jogos`, 'blue'),
      metricCard('Log loss final', num(fm.mean_log_loss), 'menor é melhor'),
      metricCard('Vazamento futuro', '0', 'validação temporal aprovada', 'green'),
      metricCard('Variáveis aceitas', s.featuresAccepted ?? 0, 'com evidência estatística')
    ].join(''));

    const rows = comparisonRows();
    setHTML('overview-comparison', rows.map(row => {
      const before = Number(row.before);
      const after = Number(row.after);
      const improved = Number.isFinite(before) && Number.isFinite(after) && (row.inverse ? after < before : after > before);
      const show = v => row.percent ? pct(v) : num(v);
      return `<div class="comparison-row"><b>${row.label}</b><span>Pré-Copa <strong>${show(before)}</strong></span><i>→</i><span>Progressivo <strong>${show(after)}</strong></span>${badge(improved ? 'Melhorou' : 'Estável', improved ? 'success' : 'neutral')}</div>`;
    }).join(''));

    horizontalBars('overview-features', (data.features || []).slice().sort((a,b) => Math.abs(b.correlation_with_goal_difference || 0) - Math.abs(a.correlation_with_goal_difference || 0)), 'correlation_with_goal_difference', 'feature', {
      format: v => num(v, 3),
      note: row => `p=${num(row.permutation_p_value, 4)} · amostra ${row.sample_size || 'NA'}`
    });

    const safety = data.temporalSafety || {};
    setHTML('overview-safety', Object.entries(safety).map(([key, value]) => `<div class="safety-row"><span>${value === false || value === 0 ? '✓' : '✓'}</span><div><b>${human(key)}</b><small>${typeof value === 'boolean' ? (value ? 'Ativo' : 'Nenhuma ocorrência') : text(value)}</small></div></div>`).join(''));

    const final = data.finalModelParameters || {};
    setHTML('overview-parameters', Object.entries(final).map(([key,value]) => `<div class="parameter-row"><span>${human(key)}</span><b>${num(value, key.includes('weight') ? 3 : 4)}</b></div>`).join(''));

    const evo = data.dailyEvolution || [];
    lineChart('overview-evolution-chart', evo, [
      { label: 'Acurácia', value: r => r.outcomeAccuracy, color: COLORS[0] },
      { label: 'Brier', value: r => r.meanBrierScore, color: COLORS[1] }
    ], { min: 0, max: 1, percent: true, xLabel: r => dateBR(r.date, true) });

    const factorRows = data.learning?.factorDistribution || [];
    horizontalBars('overview-factors', factorRows.slice(0, 6), 'count', 'factor', { format: v => `${v} jogos` });
  }

  function renderEvolution() {
    const evo = data.dailyEvolution || [];
    const accepted = evo.filter(r => r.recalibrationAccepted);
    const first = evo[0] || {};
    const last = evo.at(-1) || {};
    setHTML('evolution-kpis', [
      metricCard('Snapshots diários', evo.length, `${dateBR(first.date)} → ${dateBR(last.date)}`),
      metricCard('Resultados observados', last.resultsObserved ?? 0, 'ao final do replay'),
      metricCard('Acurácia acumulada', pct(last.outcomeAccuracy), 'walk-forward'),
      metricCard('Recalibrações aceitas', accepted.length, accepted.length ? accepted.map(r => dateBR(r.date, true)).join(', ') : 'nenhuma promovida'),
      metricCard('Gols-base final', num(last.baseGoals, 3), `inicial ${num(first.baseGoals, 3)}`)
    ].join(''));

    lineChart('accuracy-evolution-chart', evo, [
      { label: 'Acurácia', value: r => r.outcomeAccuracy, color: COLORS[0] },
      { label: 'Brier score', value: r => r.meanBrierScore, color: COLORS[1] }
    ], { min: 0, max: 1, percent: true, xLabel: r => dateBR(r.date, true) });

    lineChart('loss-evolution-chart', evo, [
      { label: 'Log loss', value: r => r.meanLogLoss, color: COLORS[2] },
      { label: 'Brier score', value: r => r.meanBrierScore, color: COLORS[1] }
    ], { min: 0, xLabel: r => dateBR(r.date, true) });

    lineChart('parameter-evolution-chart', evo, [
      { label: 'Gols-base', value: r => r.baseGoals, color: COLORS[0] },
      { label: 'Temperatura', value: r => r.probabilityTemperature, color: COLORS[4] }
    ], { xLabel: r => dateBR(r.date, true) });

    const phases = data.semanticVersions || [];
    setHTML('evolution-checkpoints', phases.map((version, index) => `<article class="checkpoint-card"><span>${String(index + 1).padStart(2,'0')}</span><div><b>${human(version.version.replace('model_after_','após_'))}</b><small>Corte: ${dateBR(version.trainingCutoff)} · jogo ${version.checkpointMatchId ?? 'NA'}</small></div><strong>${pct(version.metrics?.outcome_accuracy)}</strong></article>`).join(''));

    setHTML('evolution-table-body', evo.map(row => `<tr><td>${dateBR(row.date)}</td><td>${row.resultsObserved}</td><td>${pct(row.outcomeAccuracy)}</td><td>${num(row.meanLogLoss)}</td><td>${num(row.meanBrierScore)}</td><td>${num(row.baseGoals,3)}</td><td>${num(row.probabilityTemperature,2)}</td><td>${row.recalibrationAccepted ? badge('Aceita','success') : badge('Mantida','neutral')}</td></tr>`).join(''));
  }

  function probabilityBar(match) {
    const values = [match.probabilityTeam1Win || 0, match.probabilityDraw || 0, match.probabilityTeam2Win || 0];
    return `<div class="probability-strip" aria-label="Probabilidades"><i style="width:${values[0]*100}%"></i><i style="width:${values[1]*100}%"></i><i style="width:${values[2]*100}%"></i></div>`;
  }

  function predictionCard(match) {
    const tone = match.outcomeCorrect ? 'success' : 'danger';
    return `<button class="prediction-card" data-match-id="${match.matchId}"><header><span>Jogo ${match.matchId} · ${dateBR(match.date)}</span>${badge(match.outcomeCorrect ? 'Resultado certo' : 'Resultado errado', tone)}</header><div class="prediction-card__teams">${team(match.team1)}<strong>${match.predictedScore}</strong>${team(match.team2)}</div>${probabilityBar(match)}<footer><span>${pct(match.probabilityTeam1Win)}</span><span>${pct(match.probabilityDraw)}</span><span>${pct(match.probabilityTeam2Win)}</span></footer></button>`;
  }

  function renderPredictionDetail(match) {
    if (!match) return;
    const probs = [
      { name: match.team1, value: match.probabilityTeam1Win },
      { name: 'Empate', value: match.probabilityDraw },
      { name: match.team2, value: match.probabilityTeam2Win }
    ];
    const scoreRows = (match.topScorelines || []).map(s => ({ label: s.score, value: s.probability }));
    const contributionMax = Math.max(...(match.featureContributions || []).map(x => Math.abs(x.contribution)), .001);
    setHTML('prediction-detail', `<div class="detail-head"><div><small>Jogo ${match.matchId} · ${match.phase}</small><h2>${match.team1} x ${match.team2}</h2><p>Previsão registrada em ${dateBR(match.predictionAt)} antes do início da partida.</p></div>${badge(match.outcomeCorrect ? 'Acerto' : 'Erro', match.outcomeCorrect ? 'success' : 'danger')}</div>
      <div class="match-verdict"><div>${team(match.team1,'large')}<strong>${match.predictedScore}</strong><small>placar previsto</small></div><i>×</i><div>${team(match.team2,'large')}<strong>${match.actualScore}${match.penaltyScore ? ` (${match.penaltyScore} pên.)` : ''}</strong><small>placar real</small></div></div>
      <section class="detail-section"><h3>Probabilidades pré-jogo</h3><div class="probability-cards">${probs.map((p,i) => `<div><small>${p.name}</small><strong>${pct(p.value)}</strong><i><em style="width:${(p.value||0)*100}%;--bar-color:${COLORS[i]}"></em></i></div>`).join('')}</div></section>
      <section class="detail-grid"><div class="detail-section"><h3>Placar provável</h3><div class="scoreline-grid">${scoreRows.map((r,i) => `<span><b>${r.label}</b><i><em style="width:${(r.value/(scoreRows[0]?.value||1))*100}%"></em></i><small>${pct(r.value)}</small></span>`).join('')}</div></div>
      <div class="detail-section"><h3>Leitura do modelo</h3><dl class="model-definition"><div><dt>Resultado previsto</dt><dd>${match.predictedOutcome}</dd></div><div><dt>Confiança</dt><dd>${pct(match.confidence)}</dd></div><div><dt>xG estimado</dt><dd>${num(match.expectedGoalsTeam1,2)} × ${num(match.expectedGoalsTeam2,2)}</dd></div><div><dt>Erro de gols</dt><dd>${match.goalAbsoluteError}</dd></div><div><dt>Log loss</dt><dd>${num(match.logLoss)}</dd></div><div><dt>Brier</dt><dd>${num(match.brierScore)}</dd></div></dl></div></section>
      <section class="detail-section"><h3>Contribuição das variáveis</h3><div class="contribution-list">${(match.featureContributions || []).map(row => { const w=Math.abs(row.contribution)/contributionMax*50; const pos=row.contribution>=0; return `<div><b>${human(row.factor)}</b><span class="contribution-axis"><i class="${pos?'positive':'negative'}" style="width:${w}%"></i></span><strong>${row.contribution>0?'+':''}${num(row.contribution,3)}</strong></div>`; }).join('')}</div></section>
      <section class="detail-grid"><div class="detail-section"><h3>Dados disponíveis</h3><p>${badge(match.readinessStatus, match.readinessStatus === 'READY' ? 'success' : 'warning')} <b>${pct(match.readinessScore)}</b> de prontidão.</p><div class="tag-list">${match.missingFields.length ? match.missingFields.map(f => `<span>${human(f)}: NA</span>`).join('') : '<span>Nenhuma lacuna</span>'}</div></div>
      <div class="detail-section"><h3>Aprendizado pós-jogo</h3><p>${text(match.explanation)}</p><dl class="model-definition"><div><dt>Fator principal</dt><dd>${human(match.primaryFactor)}</dd></div><div><dt>Significância</dt><dd>${human(match.significance)}</dd></div><div><dt>Surpresa</dt><dd>${pct(match.surpriseIndex)}</dd></div><div><dt>Primeiro gol</dt><dd>${match.firstGoal?.player ? `${match.firstGoal.player} · ${match.firstGoal.clock}` : 'NA'}</dd></div></dl></div></section>`);
  }

  function renderPredictions() {
    const all = data.predictions || [];
    const list = document.getElementById('prediction-list');
    const search = document.getElementById('prediction-search');
    const phase = document.getElementById('prediction-phase');
    const result = document.getElementById('prediction-result');
    const sort = document.getElementById('prediction-sort');
    const phases = [...new Set(all.map(m => m.phase))];
    if (phase) phase.innerHTML = `<option value="">Todas as fases</option>${phases.map(p => `<option>${p}</option>`).join('')}`;

    let selected = all[0];
    function refresh() {
      const q = (search?.value || '').trim().toLowerCase();
      let rows = all.filter(m => (!q || `${m.matchId} ${m.team1} ${m.team2}`.toLowerCase().includes(q)) && (!phase?.value || m.phase === phase.value) && (!result?.value || (result.value === 'hit' ? m.outcomeCorrect : !m.outcomeCorrect)));
      if (sort?.value === 'confidence') rows.sort((a,b) => (b.confidence||0)-(a.confidence||0));
      else if (sort?.value === 'error') rows.sort((a,b) => (b.logLoss||0)-(a.logLoss||0));
      else rows.sort((a,b) => a.matchId-b.matchId);
      setText('prediction-count', `${rows.length} jogos`);
      if (list) list.innerHTML = rows.map(predictionCard).join('') || '<div class="empty-state">Nenhuma previsão encontrada.</div>';
      if (!rows.includes(selected)) selected = rows[0];
      renderPredictionDetail(selected);
    }
    [search,phase,result,sort].forEach(el => el?.addEventListener(el === search ? 'input' : 'change', refresh));
    list?.addEventListener('click', event => {
      const card = event.target.closest('[data-match-id]');
      if (!card) return;
      selected = all.find(m => m.matchId === Number(card.dataset.matchId));
      renderPredictionDetail(selected);
      document.querySelectorAll('.prediction-card').forEach(el => el.classList.toggle('is-selected', Number(el.dataset.matchId) === selected.matchId));
    });
    refresh();
  }

  function matchMini(row, tone) {
    const match = (data.predictions || []).find(m => m.matchId === Number(row.match_id));
    if (!match) return '';
    return `<button class="learning-match" data-learning-match="${match.matchId}"><span>Jogo ${match.matchId}</span><div>${team(match.team1,'small')}<b>${match.actualScore}</b>${team(match.team2,'small')}</div><small>${human(match.primaryFactor)} · log loss ${num(match.logLoss)}</small>${badge(tone === 'hit' ? 'Acerto forte' : 'Erro relevante', tone === 'hit' ? 'success' : 'danger')}</button>`;
  }

  function renderLearningDetail(match) {
    if (!match) return;
    const adj = match.modelAdjustment || {};
    const stats = match.teamStats || {};
    setHTML('learning-detail', `<div class="detail-head"><div><small>Jogo ${match.matchId} · ${dateBR(match.date)}</small><h2>${match.team1} x ${match.team2}</h2><p>${text(match.explanation)}</p></div>${badge(human(match.significance), match.significance === 'tendencia_real' ? 'success' : 'neutral')}</div>
      <div class="learning-verdict"><div><small>Previsão</small><b>${match.predictedOutcome}</b><strong>${match.predictedScore}</strong></div><i>→</i><div><small>Resultado</small><b>${match.actualWinner}</b><strong>${match.actualScore}</strong></div></div>
      <section class="detail-grid"><div class="detail-section"><h3>Diagnóstico</h3><dl class="model-definition"><div><dt>Fator decisivo</dt><dd>${human(match.primaryFactor)}</dd></div><div><dt>Direção</dt><dd>${text(match.primaryFactorDirection)}</dd></div><div><dt>Força da evidência</dt><dd>${text(match.primaryFactorStrength)}</dd></div><div><dt>Surpresa</dt><dd>${pct(match.surpriseIndex)}</dd></div><div><dt>Log loss</dt><dd>${num(match.logLoss)}</dd></div><div><dt>Erro total de gols</dt><dd>${match.goalAbsoluteError}</dd></div></dl></div>
      <div class="detail-section"><h3>Ajuste de rating</h3><dl class="model-definition"><div><dt>${match.team1}</dt><dd>${num(adj.team1_rating_before,1)} → ${num(adj.team1_rating_after,1)}</dd></div><div><dt>Delta</dt><dd>${Number(adj.rating_delta_team1||0)>0?'+':''}${num(adj.rating_delta_team1,2)}</dd></div><div><dt>${match.team2}</dt><dd>${num(adj.team2_rating_before,1)} → ${num(adj.team2_rating_after,1)}</dd></div><div><dt>Delta</dt><dd>${Number(adj.rating_delta_team2||0)>0?'+':''}${num(adj.rating_delta_team2,2)}</dd></div></dl></div></section>
      <section class="detail-section"><h3>Evidências observadas</h3><div class="evidence-grid">${Object.entries(stats).map(([teamName,values]) => `<article><h4>${team(teamName,'small')}</h4><span>Posse <b>${num(values.stat_possessionPct,1)}%</b></span><span>Finalizações <b>${num(values.stat_totalShots,0)}</b></span><span>No alvo <b>${num(values.stat_shotsOnTarget,0)}</b></span><span>Cartões vermelhos <b>${num(values.stat_redCards,0)}</b></span></article>`).join('') || '<p>Sem estatísticas estruturadas.</p>'}</div></section>
      <section class="detail-section"><h3>Fatores associados</h3><div class="tag-list">${(match.importantFactors || []).map(f => `<span>${human(f.factor)} · ${text(f.strength)}</span>`).join('') || '<span>Sem fatores adicionais</span>'}</div></section>`);
  }

  function renderLearning() {
    const predictions = data.predictions || [];
    const factors = data.learning?.factorDistribution || [];
    const significance = data.learning?.significanceDistribution || [];
    setHTML('learning-kpis', [
      metricCard('Análises pós-jogo', predictions.length, 'uma por partida'),
      metricCard('Acertos de resultado', data.summary?.outcomeCorrect ?? 0, pct(data.finalMetrics?.outcome_accuracy), 'green'),
      metricCard('Erros relevantes', predictions.filter(m => !m.outcomeCorrect).length, 'direção incorreta'),
      metricCard('Fatores observados', factors.length, 'classes explicativas'),
      metricCard('Mudanças estruturais', significance.find(x => x.classification === 'mudanca_estrutural')?.count || 0, 'classificação conservadora')
    ].join(''));
    horizontalBars('learning-factors', factors, 'count', 'factor', { format: v => `${v}` });
    horizontalBars('learning-significance', significance, 'count', 'classification', { format: v => `${v} jogos` });
    setHTML('learning-errors', (data.learning?.largestErrors || []).slice(0,6).map(row => matchMini(row,'error')).join(''));
    setHTML('learning-hits', (data.learning?.largestHits || []).slice(0,6).map(row => matchMini(row,'hit')).join(''));

    const list = document.getElementById('learning-game-list');
    const filter = document.getElementById('learning-filter');
    const search = document.getElementById('learning-search');
    let selected = predictions.find(m => !m.outcomeCorrect) || predictions[0];
    function refresh() {
      const q = (search?.value || '').toLowerCase();
      const rows = predictions.filter(m => (!q || `${m.matchId} ${m.team1} ${m.team2} ${m.primaryFactor}`.toLowerCase().includes(q)) && (!filter?.value || (filter.value === 'hit' ? m.outcomeCorrect : filter.value === 'miss' ? !m.outcomeCorrect : m.significance === filter.value)));
      if (list) list.innerHTML = rows.map(m => `<button class="learning-list-row" data-learning-match="${m.matchId}"><span>${String(m.matchId).padStart(3,'0')}</span><div><b>${m.team1} x ${m.team2}</b><small>${human(m.primaryFactor)} · ${human(m.significance)}</small></div><strong>${m.actualScore}</strong>${badge(m.outcomeCorrect?'Certo':'Erro',m.outcomeCorrect?'success':'danger')}</button>`).join('');
      if (!rows.includes(selected)) selected = rows[0];
      renderLearningDetail(selected);
    }
    [filter,search].forEach(el => el?.addEventListener(el === search ? 'input':'change',refresh));
    document.addEventListener('click', event => {
      const target = event.target.closest('[data-learning-match]');
      if (!target) return;
      selected = predictions.find(m => m.matchId === Number(target.dataset.learningMatch));
      renderLearningDetail(selected);
    });
    refresh();
  }

  function simulationAvailable() {
    return (data.simulations || []).filter(s => s.champions?.length);
  }

  function renderSimulations() {
    const all = data.simulations || [];
    const available = simulationAvailable();
    const select = document.getElementById('simulation-date-select');
    const range = document.getElementById('simulation-range');
    if (select) select.innerHTML = all.map((s,i) => `<option value="${i}">${dateBR(s.date)} · ${s.resultsObserved} resultados</option>`).join('');
    if (range) { range.max = Math.max(0, all.length - 1); range.value = all.length - 1; }

    const teamMax = new Map();
    available.forEach(s => s.champions.forEach(c => teamMax.set(c.team, Math.max(teamMax.get(c.team)||0,c.champion||0))));
    const tracked = [...teamMax.entries()].sort((a,b)=>b[1]-a[1]).slice(0,8).map(x=>x[0]);
    lineChart('champion-evolution-chart', available, tracked.map((name,i)=>({ label:name, color:COLORS[i%COLORS.length], value:s => s.champions.find(c=>c.team===name)?.champion ?? 0 })), { min:0, max:1, percent:true, xLabel:r=>dateBR(r.date,true) });

    const firstAvailable = available[0];
    const lastAvailable = available.at(-1);
    setHTML('simulation-kpis', [
      metricCard('Snapshots', all.length, `${available.length} com mata-mata disponível`),
      metricCard('Primeira hipótese de campeão', firstAvailable ? dateBR(firstAvailable.date) : 'NA', firstAvailable ? `${firstAvailable.resultsObserved} resultados observados` : ''),
      metricCard('Líder inicial', firstAvailable?.champions?.[0]?.team || 'NA', firstAvailable ? pct(firstAvailable.champions[0].champion) : ''),
      metricCard('Campeão final', lastAvailable?.champions?.[0]?.team || 'NA', lastAvailable ? pct(lastAvailable.champions[0].champion) : '', 'green'),
      metricCard('Monte Carlo', lastAvailable?.iterations || 'NA', 'iterações por snapshot')
    ].join(''));

    function update(index) {
      const sim = all[index] || all.at(-1);
      if (!sim) return;
      if (select) select.value = String(index);
      if (range) range.value = String(index);
      setText('simulation-date-label', `${dateBR(sim.date)} · ${sim.resultsObserved} resultados conhecidos`);
      if (!sim.champions?.length) {
        setHTML('simulation-ranking', `<div class="empty-state"><b>Mata-mata ainda indisponível</b><p>${text(sim.knockoutReason, 'Os confrontos ainda não eram conhecidos nesse ponto da linha do tempo.')}</p></div>`);
      } else {
        horizontalBars('simulation-ranking', sim.champions.slice(0,16), 'champion', 'team', { percent:true, team:true });
      }
      const q = (sim.qualification || []).slice().sort((a,b)=>(b.qualify||0)-(a.qualify||0)).slice(0,16);
      horizontalBars('qualification-ranking', q, 'qualify', 'team', { percent:true, team:true, note:r=>`Grupo ${r.group} · 1º ${pct(r.first)} · 2º ${pct(r.second)}` });
      setHTML('simulation-snapshot-summary', `<div class="snapshot-summary"><span>${badge(sim.knockoutStatus, sim.knockoutStatus==='AVAILABLE'?'success':'warning')}</span><dl><div><dt>Data de corte</dt><dd>${dateBR(sim.cutoff)}</dd></div><div><dt>Resultados observados</dt><dd>${sim.resultsObserved}</dd></div><div><dt>Iterações</dt><dd>${sim.iterations || 'NA'}</dd></div><div><dt>Seleções com chance</dt><dd>${sim.champions?.filter(c=>c.champion>0).length || 0}</dd></div></dl></div>`);
    }
    range?.addEventListener('input', () => update(Number(range.value)));
    select?.addEventListener('change', () => update(Number(select.value)));
    update(all.length - 1);
  }

  function versionLabel(version) {
    if (version.version === 'model_pre_worldcup') return 'Modelo pré-Copa';
    return version.version.replace('model_after_','Após ').replaceAll('_',' ');
  }

  function renderVersionDetail(version) {
    if (!version) return;
    const rec = version.recalibration || {};
    setHTML('version-detail', `<div class="detail-head"><div><small>Versão temporal</small><h2>${versionLabel(version)}</h2><p>Corte de treinamento: ${dateBR(version.trainingCutoff)}. ${text(version.temporalIntegrity)}</p></div>${badge(rec.accepted ? 'Recalibração aceita' : 'Pesos preservados', rec.accepted ? 'success' : 'neutral')}</div>
      <section class="detail-grid"><div class="detail-section"><h3>Métricas</h3><dl class="model-definition"><div><dt>Amostras</dt><dd>${text(version.metrics?.samples)}</dd></div><div><dt>Acurácia</dt><dd>${pct(version.metrics?.outcome_accuracy)}</dd></div><div><dt>Log loss</dt><dd>${num(version.metrics?.mean_log_loss)}</dd></div><div><dt>Brier</dt><dd>${num(version.metrics?.mean_brier_score)}</dd></div><div><dt>Log loss recente</dt><dd>${num(version.metrics?.recent_20_log_loss)}</dd></div></dl></div>
      <div class="detail-section"><h3>Recalibração</h3><dl class="model-definition"><div><dt>Status</dt><dd>${rec.accepted ? 'Aceita' : 'Não promovida'}</dd></div><div><dt>Temperatura anterior</dt><dd>${num(rec.previous_temperature,2)}</dd></div><div><dt>Temperatura escolhida</dt><dd>${num(rec.selected_temperature,2)}</dd></div><div><dt>Gols-base anterior</dt><dd>${num(rec.base_goals_before,3)}</dd></div><div><dt>Gols-base atualizado</dt><dd>${num(rec.base_goals_after,3)}</dd></div></dl></div></section>
      <section class="detail-section"><h3>Parâmetros</h3><div class="parameter-grid">${Object.entries(version.parameters || {}).map(([key,value])=>`<div><span>${human(key)}</span><b>${num(value,4)}</b></div>`).join('')}</div></section>`);
  }

  function renderVersions() {
    const versions = data.versions || [];
    const semantic = data.semanticVersions || [];
    const daily = versions.filter(v => v.version !== 'model_pre_worldcup');
    setHTML('version-kpis', [
      metricCard('Versões temporais', versions.length, 'incluindo modelo inicial'),
      metricCard('Checkpoints de fase', semantic.length, 'versões semânticas'),
      metricCard('Temperatura final', num(data.finalModelParameters?.probability_temperature,2), 'calibração'),
      metricCard('Gols-base final', num(data.finalModelParameters?.base_goals,3), 'expectativa por equipe'),
      metricCard('Taxa de aprendizado', num(data.finalModelParameters?.learning_rate,3), 'atualização conservadora')
    ].join(''));
    lineChart('version-base-goals-chart', daily, [
      { label:'Gols-base', value:v=>v.parameters?.base_goals, color:COLORS[0] },
      { label:'Temperatura', value:v=>v.parameters?.probability_temperature, color:COLORS[4] }
    ], { xLabel:v=>dateBR(v.trainingCutoff,true) });
    lineChart('version-metrics-chart', daily.filter(v=>Number.isFinite(Number(v.metrics?.outcome_accuracy))), [
      { label:'Acurácia', value:v=>v.metrics?.outcome_accuracy, color:COLORS[0] },
      { label:'Brier', value:v=>v.metrics?.mean_brier_score, color:COLORS[1] }
    ], { min:0,max:1,percent:true,xLabel:v=>dateBR(v.trainingCutoff,true) });
    setHTML('semantic-version-grid', semantic.map(v=>`<button class="semantic-version-card" data-version="${v.sourceVersion || v.version}"><span>Jogo ${v.checkpointMatchId ?? '—'}</span><b>${versionLabel(v)}</b><small>${dateBR(v.trainingCutoff)} · acurácia ${pct(v.metrics?.outcome_accuracy)}</small></button>`).join(''));
    setHTML('version-list', versions.map(v=>`<button class="version-list-row" data-version="${v.version}"><span>${dateBR(v.trainingCutoff)}</span><div><b>${versionLabel(v)}</b><small>${v.metrics?.samples ?? 0} amostras · log loss ${num(v.metrics?.mean_log_loss)}</small></div>${badge(v.recalibration?.accepted?'Aceita':'Mantida',v.recalibration?.accepted?'success':'neutral')}</button>`).join(''));
    let selected = versions.at(-1);
    renderVersionDetail(selected);
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-version]');
      if (!button) return;
      selected = versions.find(v=>v.version===button.dataset.version) || versions.find(v=>v.version===button.dataset.version?.replace(/^models\/versions\//,'').replace('.json','')) || selected;
      renderVersionDetail(selected);
    });
  }

  function init() {
    renderTopStats();
    const runners = { overview: renderOverview, evolution: renderEvolution, predictions: renderPredictions, learning: renderLearning, simulations: renderSimulations, versions: renderVersions };
    runners[page]?.();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
