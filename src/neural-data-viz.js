(function () {
  if (document.body?.dataset?.page !== 'neural-network') return;

  const metrics = window.WC2026_REDE_NEURAL_METRICAS || {};
  const history = window.WC2026_REDE_NEURAL_HISTORICO || [];
  const predictions = window.WC2026_REDE_NEURAL_PREVISOES || [];
  const teams = window.WC2026_REDE_NEURAL_TEAMS || [];

  const COLORS = {
    text: '#f8fafc',
    muted: '#94a3b8',
    line: 'rgba(148,163,184,.22)',
    grid: 'rgba(148,163,184,.12)',
    green: '#22c55e',
    blue: '#60a5fa',
    amber: '#f59e0b',
    red: '#ef4444',
    violet: '#a78bfa'
  };

  function toNum(value, fallback = 0) {
    const n = Number(String(value ?? '').replace('%', '').replace(',', '.'));
    return Number.isFinite(n) ? n : fallback;
  }

  function parseScore(score) {
    const m = String(score || '').replace(/\s/g, '').match(/^(\d+)(?:-|x|:)(\d+)/i);
    return m ? [Number(m[1]), Number(m[2])] : null;
  }

  function winner(team1, team2, score) {
    const s = parseScore(score);
    if (!s) return '—';
    if (s[0] > s[1]) return team1;
    if (s[1] > s[0]) return team2;
    return 'Empate';
  }

  function canvasSetup(canvas) {
    if (!canvas) return null;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, width: rect.width, height: rect.height };
  }

  function drawAxes(ctx, width, height, pad, xLabel, yLabel) {
    ctx.strokeStyle = COLORS.line;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, height - pad.bottom);
    ctx.lineTo(width - pad.right, height - pad.bottom);
    ctx.stroke();

    ctx.fillStyle = COLORS.muted;
    ctx.font = '11px Inter, system-ui, sans-serif';
    if (xLabel) ctx.fillText(xLabel, width - pad.right - 90, height - 10);
    if (yLabel) {
      ctx.save();
      ctx.translate(14, pad.top + 90);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(yLabel, 0, 0);
      ctx.restore();
    }
  }

  function drawLineChart(canvas, rows) {
    const setup = canvasSetup(canvas);
    if (!setup || !rows.length) return;
    const { ctx, width, height } = setup;
    const pad = { left: 42, right: 18, top: 20, bottom: 32 };
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;
    const train = rows.map(r => toNum(r.train_loss));
    const val = rows.map(r => toNum(r.val_loss));
    const maxY = Math.max(...train, ...val, 1);
    const minY = Math.min(...train, ...val, 0);

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(255,255,255,.015)';
    ctx.fillRect(0, 0, width, height);

    for (let i = 0; i <= 4; i++) {
      const y = pad.top + chartH * i / 4;
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
    }
    drawAxes(ctx, width, height, pad, 'Épocas', 'Loss');

    function line(values, color) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      values.forEach((v, i) => {
        const x = pad.left + (rows.length <= 1 ? 0 : i / (rows.length - 1)) * chartW;
        const y = pad.top + (1 - ((v - minY) / Math.max(.0001, maxY - minY))) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    line(train, COLORS.green);
    line(val, COLORS.blue);

    const last = rows[rows.length - 1] || {};
    ctx.fillStyle = COLORS.text;
    ctx.font = '700 13px Inter, system-ui, sans-serif';
    ctx.fillText(`epoch ${last.epoch || rows.length}`, pad.left, 17);
    ctx.fillStyle = COLORS.green;
    ctx.fillText(`train ${Number(last.train_loss || 0).toFixed(3)}`, pad.left + 90, 17);
    ctx.fillStyle = COLORS.blue;
    ctx.fillText(`val ${Number(last.val_loss || 0).toFixed(3)}`, pad.left + 190, 17);
  }

  function drawDailyChart(canvas, rows) {
    const setup = canvasSetup(canvas);
    if (!setup || !rows.length) return;
    const { ctx, width, height } = setup;
    const pad = { left: 38, right: 14, top: 22, bottom: 30 };
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;
    const valid = rows.filter(r => toNum(r.jogos_validados) > 0);
    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + chartH * i / 4;
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
    }
    drawAxes(ctx, width, height, pad, 'Dias', 'Acurácia');

    const barW = Math.max(3, chartW / Math.max(1, valid.length) * .58);
    valid.forEach((r, i) => {
      const x = pad.left + (i + .5) * chartW / valid.length - barW / 2;
      const acc = toNum(r['acuracia_vencedor_%']);
      const exact = toNum(r['placar_exato_%']);
      const h = chartH * acc / 100;
      const eh = chartH * exact / 100;
      ctx.fillStyle = 'rgba(96,165,250,.72)';
      ctx.fillRect(x, pad.top + chartH - h, barW, h);
      ctx.fillStyle = 'rgba(34,197,94,.82)';
      ctx.fillRect(x + barW * .15, pad.top + chartH - eh, barW * .7, eh);
    });

    ctx.fillStyle = COLORS.blue;
    ctx.font = '700 12px Inter, system-ui, sans-serif';
    ctx.fillText('vencedor', pad.left, 16);
    ctx.fillStyle = COLORS.green;
    ctx.fillText('placar exato', pad.left + 76, 16);
  }

  function renderFeatureBars() {
    const target = document.getElementById('feature-impact-bars');
    if (!target) return;
    const rows = (window.WC2026_REDE_NEURAL_SCHEMA || []).slice(0, 10).map((row, index) => ({
      label: row.feature || `feature_${index}`,
      influence: row.uso || row.tipo || 'entrada da rede neural',
      pct: Math.max(8, 100 - index * 8)
    }));
    target.innerHTML = rows.map(row => `<div class="feature-bar-row">
      <div><b>${row.label}</b><span>${row.influence}</span></div>
      <strong>NN</strong>
      <i><em style="width:${Math.max(4, Math.min(100, row.pct))}%"></em></i>
    </div>`).join('');
  }

  function drawTeamMap(canvas, rows) {
    const setup = canvasSetup(canvas);
    if (!setup || !rows.length) return;
    const { ctx, width, height } = setup;
    const pad = { left: 52, right: 24, top: 28, bottom: 42 };
    const chartW = width - pad.left - pad.right;
    const chartH = height - pad.top - pad.bottom;
    const xs = rows.map(r => toNum((r.league_score_top11 || r.league_score_mean)));
    const ys = rows.map(r => toNum((r.player_proxy_top18 || r.player_proxy_mean)));
    const ss = rows.map(r => toNum(r.forca_modelo_0_100));
    const minX = Math.min(...xs) - 2;
    const maxX = Math.max(...xs) + 2;
    const minY = Math.min(...ys) - 2;
    const maxY = Math.max(...ys) + 2;
    const minS = Math.min(...ss);
    const maxS = Math.max(...ss);

    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + chartH * i / 4;
      const x = pad.left + chartW * i / 4;
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, height - pad.bottom); ctx.stroke();
    }
    drawAxes(ctx, width, height, pad, 'Competitividade da liga', 'Desempenho jogadores');

    const sorted = [...rows].sort((a,b) => toNum(a.forca_modelo_0_100) - toNum(b.forca_modelo_0_100));
    sorted.forEach(row => {
      const xVal = toNum((row.league_score_top11 || row.league_score_mean));
      const yVal = toNum((row.player_proxy_top18 || row.player_proxy_mean));
      const sVal = toNum(row.forca_modelo_0_100);
      const x = pad.left + ((xVal - minX) / Math.max(.0001, maxX - minX)) * chartW;
      const y = pad.top + (1 - ((yVal - minY) / Math.max(.0001, maxY - minY))) * chartH;
      const r = 4 + 8 * ((sVal - minS) / Math.max(.0001, maxS - minS));
      ctx.fillStyle = 'rgba(96,165,250,.20)';
      ctx.beginPath(); ctx.arc(x, y, r + 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(34,197,94,.84)';
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      if (sVal >= maxS - 2.5) {
        ctx.fillStyle = COLORS.text;
        ctx.font = '700 11px Inter, system-ui, sans-serif';
        ctx.fillText(row.selecao || row.codigo || '', x + r + 5, y + 4);
      }
    });
  }

  function renderPredictionErrors() {
    const target = document.getElementById('prediction-error-board');
    if (!target) return;
    const finished = predictions.filter(row => row.possui_real === 'Sim' && row.placar_real && row.placar_rede_neural);
    const rows = finished.map(row => {
      const p = parseScore(row.placar_rede_neural) || [0, 0];
      const r = parseScore(row.placar_real) || [0, 0];
      const err = Math.abs(p[0] - r[0]) + Math.abs(p[1] - r[1]);
      const winPred = winner(row.equipe1, row.equipe2, row.placar_rede_neural);
      const winReal = winner(row.equipe1, row.equipe2, row.placar_real);
      const exact = row.placar_rede_neural === row.placar_real;
      return { ...row, err, winPred, winReal, exact, okWinner: winPred === winReal };
    }).sort((a, b) => b.err - a.err || Number(b.jogo) - Number(a.jogo)).slice(0, 10);

    const exactCount = finished.filter(row => row.placar_rede_neural === row.placar_real).length;
    const winnerCount = finished.filter(row => winner(row.equipe1, row.equipe2, row.placar_rede_neural) === winner(row.equipe1, row.equipe2, row.placar_real)).length;

    target.innerHTML = `
      <div class="error-summary-strip">
        <span><b>${finished.length}</b><small>jogos reais</small></span>
        <span><b>${winnerCount}</b><small>vencedor correto</small></span>
        <span><b>${exactCount}</b><small>placar exato</small></span>
      </div>
      <div class="error-list">
        ${rows.map(row => `<div class="error-row ${row.okWinner ? 'is-ok' : 'is-miss'}">
          <b>Jogo ${row.jogo}</b>
          <span>${row.equipe1} x ${row.equipe2}</span>
          <strong>${row.placar_rede_neural} → ${row.placar_real}</strong>
          <em>erro ${row.err} · ${row.okWinner ? 'vencedor certo' : 'corrigir vencedor'}</em>
        </div>`).join('')}
      </div>`;
  }


  function buildDailyRows() {
    const byDate = new Map();
    predictions.forEach(row => {
      if (!byDate.has(row.data)) byDate.set(row.data, { data: row.data, jogos_previstos: 0, jogos_validados: 0, 'acuracia_vencedor_%': '', 'placar_exato_%': '', erro_medio_total_gols: '' });
      const item = byDate.get(row.data);
      item.jogos_previstos += 1;
      if (row.possui_real === 'Sim' && row.placar_real) {
        item.jogos_validados += 1;
        const predWinner = row.vencedor_rede_neural || winner(row.equipe1, row.equipe2, row.placar_rede_neural);
        const realWinner = winner(row.equipe1, row.equipe2, row.placar_real);
        item._winnerOk = (item._winnerOk || 0) + (predWinner === realWinner ? 1 : 0);
        item._exact = (item._exact || 0) + (row.placar_rede_neural === row.placar_real ? 1 : 0);
        const p = parseScore(row.placar_rede_neural) || [0, 0];
        const r = parseScore(row.placar_real) || [0, 0];
        item._err = (item._err || 0) + Math.abs(p[0] - r[0]) + Math.abs(p[1] - r[1]);
      }
    });
    return [...byDate.values()].map(item => {
      if (item.jogos_validados) {
        item['acuracia_vencedor_%'] = Math.round((item._winnerOk || 0) / item.jogos_validados * 100);
        item['placar_exato_%'] = Math.round((item._exact || 0) / item.jogos_validados * 100);
        item.erro_medio_total_gols = ((item._err || 0) / item.jogos_validados).toFixed(2);
      }
      return item;
    });
  }

  function refresh() {
    drawLineChart(document.getElementById('training-loss-chart'), history);
    drawDailyChart(document.getElementById('daily-performance-chart'), buildDailyRows());
    drawTeamMap(document.getElementById('team-feature-map'), teams);
  }

  function init() {
    renderFeatureBars();
    renderPredictionErrors();
    refresh();
    let timer = 0;
    window.addEventListener('resize', () => {
      clearTimeout(timer);
      timer = setTimeout(refresh, 80);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
