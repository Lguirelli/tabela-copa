
const corrections = window.WC2026_CORRECTIONS || [];
const metrics = window.WC2026_MODEL_METRICS || {};
const predictions = window.WC2026_PREDICTIONS || [];
const teamAssets = window.WC2026_TEAM_ASSETS || {};

const influenceRows = [
  {
    factor: "Resultado real",
    source: "resultados_reais / correcoes_modelo",
    impacts: "Erro, proximidade, vencedor correto e ajuste de rating",
    improvement: "Substitui a simulação e recalibra a força das equipes",
    weight: "Muito alto",
    note: "É o dado mais importante para aprendizado."
  },
  {
    factor: "Previsão anterior",
    source: "previsoes_modelo",
    impacts: "Diferença entre previsto e real",
    improvement: "Cria a referência para medir quanto o modelo errou",
    weight: "Muito alto",
    note: "Sem previsão anterior não existe correção mensurável."
  },
  {
    factor: "Força da seleção",
    source: "team_strengths",
    impacts: "xG, placar previsto, vencedor provável e confiança",
    improvement: "Ajusta favoritismo inicial antes do resultado real",
    weight: "Alto",
    note: "Resume elenco, setores, experiência e forma proxy."
  },
  {
    factor: "Estilo do técnico",
    source: "teams_tactical",
    impacts: "Ritmo, posse, pressão, transição e risco tático",
    improvement: "Ajuda a corrigir confrontos de estilos incompatíveis",
    weight: "Médio/alto",
    note: "É qualitativo, então precisa de validação por jogo."
  },
  {
    factor: "Arbitragem",
    source: "simulated_referee_assignments",
    impacts: "Cartões proxy, fluidez e jogo físico",
    improvement: "Reduz erro em jogos travados, abertos ou com muito contato",
    weight: "Médio",
    note: "Como é simulado, não deve ter peso maior que resultado real."
  },
  {
    factor: "Erro total de gols",
    source: "correcoes_modelo",
    impacts: "Precisão do placar",
    improvement: "Corrige tendência de superestimar ou subestimar gols",
    weight: "Alto",
    note: "Mostra quando o modelo acertou vencedor mas errou volume."
  },
  {
    factor: "Erro de saldo",
    source: "correcoes_modelo",
    impacts: "Leitura de domínio entre equipes",
    improvement: "Ajusta força relativa para próximos confrontos",
    weight: "Alto",
    note: "Especialmente relevante no mata-mata."
  },
  {
    factor: "Confiança do modelo",
    source: "previsoes_modelo",
    impacts: "Risco da previsão",
    improvement: "Permite marcar jogos que precisam de revisão manual",
    weight: "Médio",
    note: "Baixa confiança deve gerar alerta, não decisão automática."
  },
  {
    factor: "Assets e cores",
    source: "assets/teams / team_colors",
    impacts: "Leitura visual",
    improvement: "Melhora a interface, mas não altera o modelo",
    weight: "Visual",
    note: "Não deve influenciar previsão."
  }
];

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function colorKey(value) {
  return normalize(value).replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
}

function safe(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
}

function avg(values) {
  const nums = values.map(Number).filter((v) => Number.isFinite(v));
  return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
}

function pct(value) {
  return `${Number(value || 0).toFixed(1).replace(".0", "")}%`;
}

function getTeamAsset(team) {
  const direct = teamAssets[team];
  if (direct) return direct;
  const key = colorKey(team);
  const foundName = Object.keys(teamAssets).find((name) => colorKey(name) === key);
  return foundName ? teamAssets[foundName] : null;
}

function teamLabel(team) {
  const asset = getTeamAsset(team);
  const icon = asset?.icon || asset?.flagPng || asset?.flag;
  const img = icon ? `<img class="team-flag-icon" src="${safe(icon)}" alt="" loading="lazy" decoding="async" />` : "";
  return `<span class="team-chip">${img}<span class="team-chip__name">${safe(team)}</span></span>`;
}

function renderKpis() {
  document.getElementById("ana-corrections").textContent = metrics.jogos_com_correcao || corrections.length || "—";
  document.getElementById("ana-winner-accuracy").textContent = metrics.acuracia_vencedor_percentual ? `${metrics.acuracia_vencedor_percentual}%` : pct((corrections.filter(c => c.acertou_vencedor === "Sim").length / Math.max(corrections.length, 1)) * 100);
  document.getElementById("ana-avg-error").textContent = metrics.erro_medio_total_gols ?? avg(corrections.map(c => c.erro_total_gols)).toFixed(2);
  document.getElementById("ana-proximity").textContent = metrics.proximidade_media_0_100 ? `${metrics.proximidade_media_0_100}%` : pct(avg(corrections.map(c => c.proximidade_0_100)));
}

function renderInfluenceTable() {
  const body = document.getElementById("influence-body");
  body.innerHTML = influenceRows.map(row => `
    <tr>
      <td><strong>${safe(row.factor)}</strong></td>
      <td><code>${safe(row.source)}</code></td>
      <td>${safe(row.impacts)}</td>
      <td>${safe(row.improvement)}</td>
      <td><span class="status ${row.weight.includes("Alto") ? "status--done" : "status--sim"}">${safe(row.weight)}</span></td>
      <td class="muted">${safe(row.note)}</td>
    </tr>
  `).join("");
}

function bucketCorrections() {
  const buckets = [
    {label: "Placar exato", test: c => c.acertou_placar_exato === "Sim"},
    {label: "Vencedor correto", test: c => c.acertou_vencedor === "Sim" && c.acertou_placar_exato !== "Sim"},
    {label: "Vencedor errado", test: c => c.acertou_vencedor !== "Sim"},
    {label: "Erro alto de gols", test: c => Number(c.erro_total_gols) >= 4}
  ];
  return buckets.map(bucket => {
    const items = corrections.filter(bucket.test);
    return {
      ...bucket,
      count: items.length,
      avgError: avg(items.map(c => c.erro_total_gols)),
      avgProximity: avg(items.map(c => c.proximidade_0_100))
    };
  });
}

function renderBuckets() {
  const container = document.getElementById("error-buckets");
  const total = Math.max(corrections.length, 1);
  container.innerHTML = bucketCorrections().map(bucket => {
    const width = Math.round((bucket.count / total) * 100);
    return `
      <div class="analysis-bucket">
        <div class="analysis-bucket__top">
          <strong>${safe(bucket.label)}</strong>
          <span>${bucket.count} jogos</span>
        </div>
        <div class="bar"><i style="width:${width}%"></i></div>
        <div class="analysis-bucket__meta">
          <span>Erro médio: ${bucket.avgError.toFixed(2)}</span>
          <span>Proximidade: ${bucket.avgProximity.toFixed(1)}%</span>
        </div>
      </div>
    `;
  }).join("");
}

function renderRefereeImpact() {
  const groups = [
    {label: "Rigor baixo", test: c => Number(c.rigor_cartoes_simulado_0_10) < 5.5},
    {label: "Rigor médio", test: c => Number(c.rigor_cartoes_simulado_0_10) >= 5.5 && Number(c.rigor_cartoes_simulado_0_10) < 7},
    {label: "Rigor alto", test: c => Number(c.rigor_cartoes_simulado_0_10) >= 7},
    {label: "Jogo fluido", test: c => Number(c.fluidez_jogo_simulada_0_10) >= 7}
  ];
  const container = document.getElementById("referee-impact");
  container.innerHTML = groups.map(group => {
    const items = corrections.filter(group.test);
    const winAcc = (items.filter(c => c.acertou_vencedor === "Sim").length / Math.max(items.length, 1)) * 100;
    return `
      <div class="analysis-bucket">
        <div class="analysis-bucket__top">
          <strong>${safe(group.label)}</strong>
          <span>${items.length} jogos</span>
        </div>
        <div class="analysis-bucket__meta">
          <span>Erro médio: ${avg(items.map(c => c.erro_total_gols)).toFixed(2)}</span>
          <span>Acerto vencedor: ${winAcc.toFixed(1)}%</span>
        </div>
      </div>
    `;
  }).join("");
}

function collectTeamAdjustments() {
  const map = new Map();
  const add = (team, adjust) => {
    if (!map.has(team)) map.set(team, {team, games: 0, adjustment: 0});
    const item = map.get(team);
    item.games += 1;
    item.adjustment += Number(adjust || 0);
  };
  corrections.forEach(c => {
    add(c.equipe1, c.ajuste_rating_equipe1);
    add(c.equipe2, c.ajuste_rating_equipe2);
  });
  return Array.from(map.values()).sort((a,b) => Math.abs(b.adjustment) - Math.abs(a.adjustment));
}

function renderTeamAdjustments() {
  const body = document.getElementById("team-adjustments-body");
  body.innerHTML = collectTeamAdjustments().slice(0, 18).map(item => {
    const dir = item.adjustment > 0.05 ? "Subiu" : item.adjustment < -0.05 ? "Caiu" : "Neutro";
    const read = item.adjustment > 0.05
      ? "O modelo estava subestimando esta seleção."
      : item.adjustment < -0.05
        ? "O modelo estava superestimando esta seleção."
        : "Sem ajuste relevante até agora.";
    return `
      <tr>
        <td>${teamLabel(item.team)}</td>
        <td>${item.games}</td>
        <td><strong>${item.adjustment > 0 ? "+" : ""}${item.adjustment.toFixed(3)}</strong></td>
        <td><span class="status ${item.adjustment >= 0 ? "status--done" : "status--sim"}">${dir}</span></td>
        <td class="muted">${read}</td>
      </tr>
    `;
  }).join("");
}

function renderCorrections() {
  const body = document.getElementById("corrections-body");
  const last = [...corrections].sort((a,b) => Number(b.jogo) - Number(a.jogo)).slice(0, 24);
  body.innerHTML = last.map(c => `
    <tr>
      <td>${c.jogo}</td>
      <td>${teamLabel(c.equipe1)} <span class="muted">x</span> ${teamLabel(c.equipe2)}</td>
      <td>${safe(c.previsao_antes)}</td>
      <td><strong class="score score--real">${safe(c.resultado_real)}</strong></td>
      <td>${c.acertou_vencedor === "Sim" ? "✅" : "⚠️"} ${safe(c.vencedor_previsto)} → ${safe(c.vencedor_real)}</td>
      <td>${safe(c.erro_total_gols)}</td>
      <td>${safe(c.proximidade_0_100)}%</td>
      <td class="muted">${safe(c.correcao_registrada)}</td>
    </tr>
  `).join("");
}

function initAnalysis() {
  renderKpis();
  renderInfluenceTable();
  renderBuckets();
  renderRefereeImpact();
  renderTeamAdjustments();
  renderCorrections();
}

initAnalysis();
