const baseData = window.WC2026_DATA || { matches: [], groups: [] };
const baseMatches = baseData.matches || [];
const groups = baseData.groups || [];
const redeNeuralMetricas = window.WC2026_REDE_NEURAL_METRICAS || {};
const redeNeuralPrevisoes = window.WC2026_REDE_NEURAL_PREVISOES || [];
const redeNeuralHistorico = window.WC2026_REDE_NEURAL_HISTORICO || [];
const redeNeuralSchema = window.WC2026_REDE_NEURAL_SCHEMA || [];
const redeNeuralTeams = window.WC2026_REDE_NEURAL_TEAMS || [];
const modeloDiarioPrevisoes = window.WC2026_MODELO_DIARIO_PREVISOES || [];
const modeloDiarioResumo = window.WC2026_MODELO_DIARIO_RESUMO || [];
const modeloDiarioEstadoTimes = window.WC2026_MODELO_DIARIO_ESTADO_TIMES || [];
const modeloDiarioMetricas = window.WC2026_MODELO_DIARIO_METRICAS || {};
const activePrevisoes = window.WC2026_ACTIVE_PREVISOES || [];
const predictions = activePrevisoes.length ? activePrevisoes : (modeloDiarioPrevisoes.length ? modeloDiarioPrevisoes : redeNeuralPrevisoes);
let corrections = [];
const activeMetricas = window.WC2026_ACTIVE_METRICAS || {};
const modelMetrics = {
  ...activeMetricas,
  jogos_com_resultado_real: activeMetricas.jogos_com_placar_real_validado || redeNeuralMetricas.amostras_reais || 0,
  acuracia_vencedor_percentual: activeMetricas.acuracia_vencedor_percentual || redeNeuralMetricas.validacao_cronologica?.acuracia_vencedor || 0,
  placar_exato_percentual: activeMetricas.placar_exato_percentual || redeNeuralMetricas.validacao_cronologica?.placar_exato || 0,
  erro_medio_total_gols: activeMetricas.erro_medio_total_gols || redeNeuralMetricas.validacao_cronologica?.erro_medio_total_gols || 0,
  proximidade_media_0_100: activeMetricas.proximidade_media_0_100 || redeNeuralMetricas.proximidade_media_0_100 || 0
};
const teamAssets = window.WC2026_TEAM_ASSETS || {};

const page = document.body.dataset.page;
const predictionByGame = new Map(predictions.map((item) => [Number(item.jogo), item]));
let matches = [];
let groupPage = 0;
let groupGamesPage = 0;
let knockoutGamesPage = 0;
let bracketBaseScale = 1;
let bracketUserScale = 1;
let bracketOffset = { x: 0, y: 0 };
let bracketDragging = false;
let bracketDragStart = { x: 0, y: 0 };

const phaseLabels = {
  "16 avos de final": "16 avos",
  "Oitavas de final": "Oitavas",
  "Quartas de final": "Quartas",
  "Semifinais": "Semi",
  "Disputa de 3º lugar": "3º lugar",
  "Final": "Final"
};

const bracketLayout = {
  left: {
    r32: [73, 75, 74, 77, 83, 84, 81, 82],
    r16: [89, 90, 93, 94],
    qf: [97, 98],
    sf: [101]
  },
  right: {
    r32: [76, 78, 79, 80, 85, 87, 86, 88],
    r16: [91, 92, 96, 95],
    qf: [99, 100],
    sf: [102]
  },
  center: { final: 104, third: 103 }
};

const cardPositions = new Map();
const bracketConnections = [
  [73, 89], [75, 89], [74, 90], [77, 90], [89, 97], [90, 97], [97, 101],
  [83, 93], [84, 93], [81, 94], [82, 94], [93, 98], [94, 98], [98, 101],
  [76, 91], [78, 91], [79, 92], [80, 92], [91, 99], [92, 99], [99, 102],
  [85, 96], [87, 96], [86, 95], [88, 95], [96, 100], [95, 100], [100, 102],
  [101, 104], [102, 104], [101, 103], [102, 103]
];

const bracketParents = bracketConnections.reduce((acc, [from, to]) => {
  if (!acc[to]) acc[to] = [];
  acc[to].push(from);
  return acc;
}, {});

const bracketResolutionOrder = [
  89, 90, 93, 94, 91, 92, 96, 95,
  97, 98, 99, 100,
  101, 102,
  104, 103
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

function safeAttr(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function getTeamAsset(team) {
  const direct = teamAssets[team];
  if (direct) return direct;
  const key = colorKey(team);
  const foundName = Object.keys(teamAssets).find((name) => colorKey(name) === key);
  return foundName ? teamAssets[foundName] : null;
}

function teamChip(team, side = "left") {
  if (!team || /^([123]º|Vencedor|Perdedor|TBD)/.test(team)) {
    return `<span class="team-chip team-chip--slot"><span class="team-chip__name">${team || "—"}</span></span>`;
  }
  const asset = getTeamAsset(team);
  const iconSource = asset?.icon || asset?.flagPng || asset?.flag || "";
  const icon = iconSource
    ? `<img class="team-flag-icon" src="${safeAttr(iconSource)}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'" />`
    : `<span class="team-flag-fallback" aria-hidden="true"></span>`;
  return `<span class="team-chip team-chip--${side}" title="${safeAttr(team)}">${icon}<span class="team-chip__name">${team}</span></span>`;
}

function formatDate(dateISO) {
  if (!dateISO) return "—";
  const [year, month, day] = String(dateISO).split("-");
  return `${day}/${month}/${year}`;
}

function parseScore(score) {
  if (!score) return null;
  const clean = String(score).trim().replace(/\s/g, "");
  const found = clean.match(/^(\d+)(?:x|-|:)(\d+)$/i);
  return found ? [Number(found[1]), Number(found[2])] : null;
}

function scoreWinner(team1, team2, score, fallback = "Empate") {
  const parsed = parseScore(score);
  if (!parsed) return fallback;
  if (parsed[0] > parsed[1]) return team1;
  if (parsed[1] > parsed[0]) return team2;
  return fallback;
}

function firstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== "") || "";
}

function sameTeam(a, b) {
  return colorKey(a) === colorKey(b);
}

function isPlaceholderTeam(team) {
  return /^([123]º|Vencedor|Perdedor|TBD|Aguardando)/i.test(String(team || ""));
}

function isPredictionCompatible(match, team1 = match.equipe1, team2 = match.equipe2) {
  const predictionTeam1 = firstValue(match.prediction?.equipe1, match.prediction?.equipe1_prevista);
  const predictionTeam2 = firstValue(match.prediction?.equipe2, match.prediction?.equipe2_prevista);

  if (!predictionTeam1 || !predictionTeam2 || isPlaceholderTeam(predictionTeam1) || isPlaceholderTeam(predictionTeam2)) {
    return true;
  }

  return sameTeam(predictionTeam1, team1) && sameTeam(predictionTeam2, team2);
}

function winnerFromMatch(match) {
  if (!match) return "";
  if (match.hasReal && match.realWinner) return match.realWinner;

  const winner = firstValue(match.predictionWinner, scoreWinner(match.equipe1, match.equipe2, match.predictionScore, ""));
  if (!winner || winner === "Empate") return "";
  if (sameTeam(winner, match.equipe1)) return match.equipe1;
  if (sameTeam(winner, match.equipe2)) return match.equipe2;
  return "";
}

function loserFromMatch(match) {
  if (!match) return "";
  const winner = winnerFromMatch(match);
  if (!winner) return "";
  if (sameTeam(winner, match.equipe1)) return match.equipe2;
  if (sameTeam(winner, match.equipe2)) return match.equipe1;
  return "";
}

function pendingSlot(game, type = "winner") {
  return `${type === "loser" ? "Perdedor" : "Vencedor"} jogo ${game}`;
}

function resetPredictionForRecalculation(match, reason) {
  match.predictionScore = "";
  match.predictionWinner = "";
  match.predictionSource = "Aguardando recálculo";
  match.status = "Aguardando recálculo";
  match.scoreForTable = "";
  match.needsRecalculation = true;
  match.recalculationReason = reason || "Confronto atualizado pelo chaveamento real/projetado.";
}

function applyKnockoutProgression() {
  const byGame = new Map(matches.map((match) => [Number(match.jogo), match]));

  bracketResolutionOrder.forEach((game) => {
    const match = byGame.get(Number(game));
    const parents = bracketParents[game] || [];
    if (!match || !parents.length || match.hasReal) return;

    const isThirdPlace = Number(game) === 103;
    const firstParent = byGame.get(Number(parents[0]));
    const secondParent = byGame.get(Number(parents[1]));
    const derived1 = isThirdPlace ? loserFromMatch(firstParent) : winnerFromMatch(firstParent);
    const derived2 = isThirdPlace ? loserFromMatch(secondParent) : winnerFromMatch(secondParent);
    const nextTeam1 = derived1 || pendingSlot(parents[0], isThirdPlace ? "loser" : "winner");
    const nextTeam2 = derived2 || pendingSlot(parents[1], isThirdPlace ? "loser" : "winner");

    const changed = !sameTeam(match.equipe1, nextTeam1) || !sameTeam(match.equipe2, nextTeam2);
    match.equipe1 = nextTeam1;
    match.equipe2 = nextTeam2;
    match.confronto = `${nextTeam1} x ${nextTeam2}`;
    match.derivedFromBracket = true;

    if (changed || !isPredictionCompatible(match, nextTeam1, nextTeam2)) {
      resetPredictionForRecalculation(
        match,
        `Confronto derivado dos jogos ${parents.join(" e ")}; previsão antiga não corresponde mais aos classificados exibidos.`
      );
    }
  });
}

function buildMatches() {
  matches = baseMatches.map((base) => {
    const prediction = predictionByGame.get(Number(base.jogo)) || {};
    const predictionHasReal = prediction.possui_real === "Sim" && Boolean(prediction.placar_real);
    const baseHasReal = base.status === "Finalizado" && Boolean(base.placar_real);
    const hasReal = predictionHasReal || baseHasReal;
    const equipe1 = firstValue(base.equipe1, prediction.equipe1);
    const equipe2 = firstValue(base.equipe2, prediction.equipe2);
    const predictionScore = firstValue(prediction.placar_previsto, prediction.placar_modelo_diario, prediction.placar_rede_neural);
    const rawPredictionWinner = firstValue(prediction.vencedor_previsto, prediction.vencedor_modelo_diario, prediction.vencedor_rede_neural, scoreWinner(equipe1, equipe2, predictionScore));
    const predictionWinner = (sameTeam(rawPredictionWinner, equipe1) || sameTeam(rawPredictionWinner, equipe2) || rawPredictionWinner === "Empate")
      ? rawPredictionWinner
      : "";
    const predictionSource = firstValue(
      prediction.fonte_previsao,
      prediction.usa_desempenho_copa ? "Modelo diário recalibrado" : (prediction.placar_modelo_diario ? "Modelo diário" : "Rede neural")
    );
    const neuralScore = firstValue(prediction.placar_rede_neural_original, prediction.placar_rede_neural);
    const realScore = predictionHasReal ? prediction.placar_real : (baseHasReal ? base.placar_real : "");
    const realWinner = hasReal ? firstValue(base.vencedor_real, prediction.vencedor_real, scoreWinner(equipe1, equipe2, realScore)) : "";

    let correction = null;
    if (hasReal && predictionScore && realScore) {
      const ps = parseScore(predictionScore) || [0, 0];
      const rs = parseScore(realScore) || [0, 0];
      const error = Math.abs(ps[0] - rs[0]) + Math.abs(ps[1] - rs[1]);
      const winnerOk = predictionWinner === realWinner;
      const exact = predictionScore === realScore;
      const proximity = Math.max(0, Math.round(100 - error * 18 - (winnerOk ? 0 : 28)));
      correction = {
        jogo: base.jogo,
        equipe1,
        equipe2,
        previsao_antes: predictionScore,
        resultado_real: realScore,
        erro_total_gols: error,
        proximidade_0_100: proximity,
        acertou_vencedor: winnerOk ? "Sim" : "Não",
        acertou_placar_exato: exact ? "Sim" : "Não",
        correcao_registrada: exact ? "placar exato" : (winnerOk ? "vencedor correto" : "vencedor corrigido")
      };
    }

    return {
      ...base,
      equipe1,
      equipe2,
      prediction,
      real: hasReal ? { placar_real: realScore, vencedor_real: realWinner } : null,
      correction,
      hasReal,
      predictionScore,
      predictionWinner,
      predictionSource,
      neuralScore,
      penaltyScore: firstValue(prediction.placar_penaltis),
      decisaoPenaltis: firstValue(prediction.decisao_penaltis),
      winnerCriteria: firstValue(prediction.criterio_vencedor),
      realScore,
      realWinner,
      status: hasReal ? "Finalizado" : predictionSource,
      scoreForTable: hasReal ? realScore : predictionScore,
      needsRecalculation: false,
      recalculationReason: ""
    };
  });
  applyKnockoutProgression();
  corrections = matches.filter((match) => match.correction).map((match) => match.correction);
}
function matchByGame(game) {
  return matches.find((item) => Number(item.jogo) === Number(game));
}

function renderCommonStats() {
  const finished = matches.filter((match) => match.hasReal).length;
  const total = document.getElementById("stat-total");
  const fin = document.getElementById("stat-finished");
  const sim = document.getElementById("stat-simulated");
  const update = document.getElementById("sidebar-last-update");
  if (total) total.textContent = matches.length || 104;
  if (fin) fin.textContent = finished;
  if (sim) sim.textContent = matches.length - finished;
  if (update) update.textContent = modelMetrics.ultima_entrada_real ? formatDate(modelMetrics.ultima_entrada_real) : "—";
}

function initialStandingRows(group) {
  return Object.fromEntries((group.equipes || []).map((team) => [team, {
    team, played: 0, wins: 0, draws: 0, losses: 0, gf: 0, ga: 0, gd: 0, pts: 0
  }]));
}

function calculateStandings(group) {
  const table = initialStandingRows(group);
  matches
    .filter((match) => match.fase === "Fase de grupos" && match.grupo === group.grupo)
    .forEach((match) => {
      const score = parseScore(match.scoreForTable);
      if (!score || !table[match.equipe1] || !table[match.equipe2]) return;
      const [g1, g2] = score;
      const home = table[match.equipe1];
      const away = table[match.equipe2];
      home.played += 1; away.played += 1;
      home.gf += g1; home.ga += g2; away.gf += g2; away.ga += g1;
      if (g1 > g2) { home.wins += 1; away.losses += 1; home.pts += 3; }
      else if (g2 > g1) { away.wins += 1; home.losses += 1; away.pts += 3; }
      else { home.draws += 1; away.draws += 1; home.pts += 1; away.pts += 1; }
    });
  return Object.values(table)
    .map((row) => ({ ...row, gd: row.gf - row.ga }))
    .sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || a.team.localeCompare(b.team, "pt-BR"));
}

function groupPageSize() {
  if (window.innerWidth <= 720) return 1;
  if (window.innerWidth <= 1100) return 4;
  if (window.innerHeight < 790) return 6;
  return 12;
}

function tablePageSize() {
  if (window.innerHeight < 690) return 6;
  if (window.innerWidth <= 720) return 7;
  if (window.innerHeight < 820) return 9;
  return 12;
}

function renderSummaryCards() {
  const container = document.getElementById("summary-cards");
  if (!container) return;
  const finished = matches.filter((m) => m.hasReal).length;
  const exact = corrections.filter((c) => c.acertou_placar_exato === "Sim").length;
  const winnerOk = corrections.filter((c) => c.acertou_vencedor === "Sim").length;
  const data = [
    ["Jogos totais", matches.length],
    ["Finalizados", finished],
    ["Rede neural", matches.length - finished],
    ["Acerto vencedor", `${modelMetrics.acuracia_vencedor_percentual ?? 0}%`],
    ["Placar exato", `${modelMetrics.placar_exato_percentual ?? 0}%`]
  ];
  container.innerHTML = data.map(([label, value]) => `<div class="summary-card"><small>${label}</small><strong>${value}</strong></div>`).join("");
  const prox = document.getElementById("model-proximity");
  if (prox) prox.textContent = `Proximidade média ${modelMetrics.proximidade_media_0_100 ?? "—"}%`;
}

function renderStandingsPage() {
  const container = document.getElementById("standings-grid");
  if (!container) return;
  const size = groupPageSize();
  const pages = Math.max(1, Math.ceil(groups.length / size));
  groupPage = Math.max(0, Math.min(groupPage, pages - 1));
  const visible = groups.slice(groupPage * size, groupPage * size + size);
  container.innerHTML = visible.map((group) => {
    const rows = calculateStandings(group);
    return `<article class="standing-card">
      <h3>Grupo ${group.grupo}</h3>
      <table><thead><tr><th>#</th><th>Seleção</th><th>Pts</th><th>J</th><th>V</th><th>E</th><th>D</th><th>SG</th></tr></thead><tbody>
      ${rows.map((row, index) => `<tr><td>${index + 1}</td><td>${teamChip(row.team)}</td><td>${row.pts}</td><td>${row.played}</td><td>${row.wins}</td><td>${row.draws}</td><td>${row.losses}</td><td>${row.gd > 0 ? "+" : ""}${row.gd}</td></tr>`).join("")}
      </tbody></table>
    </article>`;
  }).join("");
  const label = document.getElementById("group-page-label");
  if (label) label.textContent = `Página ${groupPage + 1}/${pages}`;
  document.getElementById("group-prev")?.toggleAttribute("disabled", groupPage === 0);
  document.getElementById("group-next")?.toggleAttribute("disabled", groupPage >= pages - 1);
}

function renderStatus(match) {
  if (match.needsRecalculation) {
    return `<span class="status status--pending">Recalcular</span>`;
  }
  return `<span class="status ${match.hasReal ? "status--done" : "status--sim"}">${match.hasReal ? "Finalizado" : (match.predictionSource || "Modelo diário")}</span>`;
}

function renderScore(score, type = "prediction") {
  return score ? `<strong class="score score--${type}">${score}</strong>` : `<span class="muted">—</span>`;
}

function renderCorrection(match) {
  if (!match.hasReal || !match.correction) return `<span class="muted">—</span>`;
  const ok = match.correction.acertou_vencedor === "Sim";
  return `<span class="correction ${ok ? "correction--ok" : "correction--miss"}">${match.correction.proximidade_0_100}% · ${match.correction.erro_total_gols}</span>`;
}

function setupGroupFilter() {
  const filter = document.getElementById("group-filter");
  if (!filter || filter.dataset.ready) return;
  groups.forEach((group) => {
    const option = document.createElement("option");
    option.value = group.grupo;
    option.textContent = `Grupo ${group.grupo}`;
    filter.appendChild(option);
  });
  filter.dataset.ready = "1";
}

function groupGameRows() {
  const selected = document.getElementById("group-filter")?.value || "all";
  const query = normalize(document.getElementById("group-search")?.value || "");
  return matches
    .filter((m) => m.fase === "Fase de grupos")
    .filter((m) => selected === "all" || m.grupo === selected)
    .filter((m) => !query || normalize(`${m.equipe1} ${m.equipe2} ${m.cidade} ${m.estadio}`).includes(query))
    .sort((a, b) => a.jogo - b.jogo);
}

function renderGroupGamesPage() {
  const body = document.getElementById("group-games-body");
  if (!body) return;
  const rows = groupGameRows();
  const size = tablePageSize();
  const pages = Math.max(1, Math.ceil(rows.length / size));
  groupGamesPage = Math.max(0, Math.min(groupGamesPage, pages - 1));
  const visible = rows.slice(groupGamesPage * size, groupGamesPage * size + size);
  body.innerHTML = visible.map((m) => `<tr>
    <td>${m.jogo}</td><td>${formatDate(m.data)}</td><td>${m.grupo}</td>
    <td><div class="versus-line">${teamChip(m.equipe1)}<span>x</span>${teamChip(m.equipe2, "right")}</div></td>
    <td>${renderScore(m.predictionScore, "prediction")}</td>
    <td>${m.hasReal ? renderScore(m.realScore, "real") : `<span class="muted">—</span>`}</td>
    <td>${renderStatus(m)}</td><td>${renderCorrection(m)}</td><td>${m.cidade}</td>
  </tr>`).join("");
  const label = document.getElementById("group-games-label");
  if (label) label.textContent = `${rows.length ? groupGamesPage * size + 1 : 0}-${Math.min((groupGamesPage + 1) * size, rows.length)} de ${rows.length}`;
  document.getElementById("group-games-prev")?.toggleAttribute("disabled", groupGamesPage === 0);
  document.getElementById("group-games-next")?.toggleAttribute("disabled", groupGamesPage >= pages - 1);
}

function setupKoFilter() {
  const filter = document.getElementById("ko-phase-filter");
  if (!filter || filter.dataset.ready) return;
  [...new Set(baseMatches.filter((m) => m.fase !== "Fase de grupos").map((m) => m.fase))].forEach((phase) => {
    const option = document.createElement("option");
    option.value = phase;
    option.textContent = phaseLabels[phase] || phase;
    filter.appendChild(option);
  });
  filter.dataset.ready = "1";
}

function koGameRows() {
  const selected = document.getElementById("ko-phase-filter")?.value || "all";
  return matches
    .filter((m) => m.fase !== "Fase de grupos")
    .filter((m) => selected === "all" || m.fase === selected)
    .sort((a, b) => a.jogo - b.jogo);
}

function renderKnockoutGamesPage() {
  const body = document.getElementById("ko-games-body");
  if (!body) return;
  const rows = koGameRows();
  const size = tablePageSize();
  const pages = Math.max(1, Math.ceil(rows.length / size));
  knockoutGamesPage = Math.max(0, Math.min(knockoutGamesPage, pages - 1));
  const visible = rows.slice(knockoutGamesPage * size, knockoutGamesPage * size + size);
  body.innerHTML = visible.map((m) => `<tr>
    <td>${m.jogo}</td><td>${phaseLabels[m.fase] || m.fase}</td><td>${formatDate(m.data)}</td>
    <td><div class="versus-line">${teamChip(m.equipe1)}<span>x</span>${teamChip(m.equipe2, "right")}</div></td>
    <td>${renderScore(m.predictionScore, "prediction")}</td>
    <td>${m.hasReal ? renderScore(m.realScore, "real") : `<span class="muted">—</span>`}</td>
    <td>${renderStatus(m)}</td><td>${m.hasReal ? m.realWinner : m.predictionWinner || "—"}</td><td>${renderCorrection(m)}</td>
  </tr>`).join("");
  const label = document.getElementById("ko-games-label");
  if (label) label.textContent = `${rows.length ? knockoutGamesPage * size + 1 : 0}-${Math.min((knockoutGamesPage + 1) * size, rows.length)} de ${rows.length}`;
  document.getElementById("ko-games-prev")?.toggleAttribute("disabled", knockoutGamesPage === 0);
  document.getElementById("ko-games-next")?.toggleAttribute("disabled", knockoutGamesPage >= pages - 1);
}

function bracketCard(game, x, y, extra = "") {
  const m = matchByGame(game);
  if (!m) return "";
  const displayScore = m.hasReal ? m.realScore : m.predictionScore;
  const penaltyInfo = !m.hasReal && m.decisaoPenaltis === "Sim" && m.penaltyScore ? ` · Pên. ${m.penaltyScore}` : "";
  const class1 = Number(m.prediction?.prob_classificacao_equipe1);
  const class2 = Number(m.prediction?.prob_classificacao_equipe2);
  const classInfo = !m.hasReal && Number.isFinite(class1) && Number.isFinite(class2)
    ? ` · Class.: ${(class1 * 100).toFixed(1)}% x ${(class2 * 100).toFixed(1)}%`
    : "";
  const secondaryLabel = m.hasReal ? (m.predictionSource || "Modelo diário") : (m.needsRecalculation ? "Modelo" : "Real");
  const secondaryScore = m.hasReal ? (m.predictionScore || "—") : (m.needsRecalculation ? "recalcular" : (penaltyInfo ? `Pên. ${m.penaltyScore}` : "—"));
  const cardState = m.hasReal ? "is-real" : (m.needsRecalculation ? "is-pending" : "is-neural");
  const statusText = m.hasReal ? "Finalizado" : (m.needsRecalculation ? "Aguardando recálculo" : (m.predictionSource || "Modelo diário"));
  const winnerText = m.hasReal
    ? `Vencedor: ${m.realWinner}`
    : (m.needsRecalculation ? "Previsto: aguardando recálculo" : `Previsto: ${m.predictionWinner || "—"}${penaltyInfo}${classInfo}`);

  cardPositions.set(game, { x, y, w: extra.includes("final") ? 260 : extra.includes("third") ? 240 : 220, h: 92 });
  return `<article class="bracket-stage ${extra} ${cardState}" data-game="${game}" title="${safeAttr(m.recalculationReason || "")}" style="left:${x}px;top:${y}px">
    <div class="bracket-meta"><span>Jogo ${m.jogo}</span><span>${phaseLabels[m.fase] || m.fase}</span></div>
    <div class="bracket-teams"><span>${teamChip(m.equipe1)}</span><span class="bracket-score ${m.hasReal ? "score--real" : "score--prediction"}">${displayScore || "—"}</span><span>${teamChip(m.equipe2, "right")}</span></div>
    <div class="bracket-real"><span>${secondaryLabel} <strong>${secondaryScore}</strong></span><span>${statusText}</span></div>
    <div class="bracket-winner">${winnerText}</div>
  </article>`;
}

function drawLine(from, to, svg) {
  const a = cardPositions.get(from);
  const b = cardPositions.get(to);
  if (!a || !b) return;
  const fromLeft = a.x < b.x;
  const x1 = fromLeft ? a.x + a.w : a.x;
  const y1 = a.y + a.h / 2;
  const x2 = fromLeft ? b.x : b.x + b.w;
  const y2 = b.y + b.h / 2;
  const mid = fromLeft ? x1 + Math.max(28, (x2 - x1) * .45) : x1 - Math.max(28, (x1 - x2) * .45);
  const color = to === 103 ? "rgba(59,130,246,.55)" : "rgba(239,68,68,.58)";
  svg += `<path d="M ${x1} ${y1} L ${mid} ${y1} L ${mid} ${y2} L ${x2} ${y2}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`;
  return svg;
}

function renderBracketPage() {
  const board = document.getElementById("bracket-board");
  if (!board) return;
  cardPositions.clear();
  const leftX = [60, 330, 600, 870];
  const rightX = [2100, 1830, 1560, 1290];
  const yR32 = [30, 205, 380, 555, 730, 905, 1080, 1255];
  const yR16 = [118, 468, 818, 1168];
  const yQF = [293, 993];
  const ySF = [643];
  let html = `<svg class="bracket-lines" viewBox="0 0 2380 1500" width="2380" height="1500">`;
  bracketConnections.forEach(([from, to]) => { html = drawLine(from, to, html) || html; });
  html += `</svg>`;
  // Need cards before lines? Positions must exist first. Build cards separately, then redraw lines after positions.
  let cards = "";
  bracketLayout.left.r32.forEach((g, i) => cards += bracketCard(g, leftX[0], yR32[i]));
  bracketLayout.left.r16.forEach((g, i) => cards += bracketCard(g, leftX[1], yR16[i]));
  bracketLayout.left.qf.forEach((g, i) => cards += bracketCard(g, leftX[2], yQF[i]));
  bracketLayout.left.sf.forEach((g, i) => cards += bracketCard(g, leftX[3], ySF[i]));
  cards += bracketCard(bracketLayout.center.final, 1060, 565, "final");
  cards += bracketCard(bracketLayout.center.third, 1070, 780, "third");
  bracketLayout.right.sf.forEach((g, i) => cards += bracketCard(g, rightX[3], ySF[i]));
  bracketLayout.right.qf.forEach((g, i) => cards += bracketCard(g, rightX[2], yQF[i]));
  bracketLayout.right.r16.forEach((g, i) => cards += bracketCard(g, rightX[1], yR16[i]));
  bracketLayout.right.r32.forEach((g, i) => cards += bracketCard(g, rightX[0], yR32[i]));
  let svg = `<svg class="bracket-lines" viewBox="0 0 2380 1500" width="2380" height="1500">`;
  bracketConnections.forEach(([from, to]) => { svg = drawLine(from, to, svg) || svg; });
  svg += `</svg>`;
  board.innerHTML = svg + cards;
  fitBracket();
  setupBracketZoom();
}

function applyBracketTransform() {
  const board = document.getElementById("bracket-board");
  if (!board) return;
  const scale = bracketBaseScale * bracketUserScale;
  board.style.transform = `translate(calc(-50% + ${bracketOffset.x}px), calc(-50% + ${bracketOffset.y}px)) scale(${scale})`;
}

function fitBracket() {
  const fit = document.getElementById("bracket-fit");
  const board = document.getElementById("bracket-board");
  if (!fit || !board) return;
  const rect = fit.getBoundingClientRect();
  bracketBaseScale = Math.min(rect.width / 2380, rect.height / 1500, 1);
  applyBracketTransform();
}

function setupBracketZoom() {
  const fit = document.getElementById("bracket-fit");
  if (!fit || fit.dataset.zoomReady) return;
  fit.dataset.zoomReady = "1";

  fit.addEventListener("wheel", (event) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.08 : 0.08;
    bracketUserScale = Math.max(0.55, Math.min(3.2, bracketUserScale + delta));
    applyBracketTransform();
  }, { passive: false });

  fit.addEventListener("pointerdown", (event) => {
    bracketDragging = true;
    bracketDragStart = { x: event.clientX - bracketOffset.x, y: event.clientY - bracketOffset.y };
    fit.setPointerCapture?.(event.pointerId);
    fit.classList.add("is-dragging");
  });

  fit.addEventListener("pointermove", (event) => {
    if (!bracketDragging) return;
    bracketOffset = { x: event.clientX - bracketDragStart.x, y: event.clientY - bracketDragStart.y };
    applyBracketTransform();
  });

  const stopDrag = (event) => {
    bracketDragging = false;
    fit.classList.remove("is-dragging");
    if (event?.pointerId !== undefined) fit.releasePointerCapture?.(event.pointerId);
  };
  fit.addEventListener("pointerup", stopDrag);
  fit.addEventListener("pointercancel", stopDrag);
  fit.addEventListener("dblclick", () => {
    bracketUserScale = 1;
    bracketOffset = { x: 0, y: 0 };
    applyBracketTransform();
  });
}


function metricValue(value, suffix = "") {
  if (value === undefined || value === null || value === "") return "—";
  return `${value}${suffix}`;
}

function renderNeuralPage() {
  const flow = document.getElementById("neural-flow");
  if (flow) {
    const steps = [
      ["1", "Entradas do repositório", "Jogadores, técnico, ligas, calendário e resultados reais."],
      ["2", "Features numéricas", "Força do elenco, competitividade da liga, desempenho dos jogadores, calendário e diferença entre equipes."],
      ["3", "Estado da Copa", "Rating atual, gols, saldo, pontos, momentum e memória de desempenho são atualizados após cada placar real."],
      ["4", "Modelo diário", "A previsão ativa vem do modelo incremental: usa dados acumulados até antes do jogo, sem vazar informação futura."],
      ["5", "Validação cronológica", "Depois do placar real, o erro é registrado e o estado de cada seleção é atualizado para os próximos jogos."],
      ["6", "Saída ativa", "O chaveamento usa placar real quando disponível; caso contrário, usa a previsão do modelo diário e mantém a rede pura como referência."]
    ];
    flow.innerHTML = steps.map(([n, title, body]) => `<div class="flow-step"><b>${n}</b><div><strong>${title}</strong><span>${body}</span></div></div>`).join("");
  }

  const metrics = document.getElementById("neural-metrics");
  if (metrics) {
    const val = redeNeuralMetricas.validacao_cronologica || {};
    const rows = [
      ["Modelo ativo", modelMetrics.modelo_ativo || modeloDiarioMetricas.modelo || "Modelo diário incremental"],
      ["Jogos reais usados", metricValue(modelMetrics.jogos_com_resultado_real)],
      ["Validação sem vazamento", modeloDiarioMetricas.validacao_sem_vazamento ? "Sim" : "—"],
      ["Acerto vencedor", metricValue(modelMetrics.acuracia_vencedor_percentual, "%")],
      ["Placar exato", metricValue(modelMetrics.placar_exato_percentual, "%")],
      ["Erro médio gols", metricValue(modelMetrics.erro_medio_total_gols)],
      ["Proximidade média", metricValue(modelMetrics.proximidade_media_0_100, "%")],
      ["Peso resultado anterior", modeloDiarioMetricas.peso_resultado_anterior || "Momentum por seleção"],
      ["Peso desempenho", modeloDiarioMetricas.peso_desempenho || "Memória de desempenho"],
      ["Rede pura", `${metricValue(val.acuracia_vencedor, "%")} vencedor, referência secundária`]
    ];
    metrics.innerHTML = rows.map(([label, value]) => `<div class="metric-row"><span>${label}</span><b>${value}</b></div>`).join("");
  }

  const weights = document.getElementById("neural-weights");
  if (weights) {
    const dailyFeatures = [
      ["feature_momentum_diff", "Diferença de momentum acumulado dentro da Copa"],
      ["feature_performance_memory_diff", "Diferença de memória de desempenho validada"],
      ["feature_rating_diff", "Rating atual já ajustado por resultados reais"],
      ["feature_base_rating_diff", "Força pré-Copa como base contextual"],
      ["feature_attack_vs_defense", "Ataque de um time contra defesa do outro"],
      ["feature_player_quality_diff", "Qualidade média dos jogadores"],
      ["feature_league_diff", "Competitividade da liga dos jogadores"],
      ["feature_rest_diff", "Diferença de descanso"],
      ["feature_knockout", "Peso de fase eliminatória"],
      ["feature_round_group", "Rodada/fase do calendário"]
    ];
    weights.innerHTML = dailyFeatures.map(([feature, uso]) => `<div class="weight-row"><div><b>${feature}</b><span>${uso}</span></div><strong>DIÁRIO</strong></div>`).join("");
  }

  const daily = document.getElementById("neural-daily-body");
  if (daily) {
    const byDate = new Map();
    const dailyRows = modeloDiarioResumo.length ? modeloDiarioResumo : null;
    if (dailyRows) {
      daily.innerHTML = dailyRows.slice(0, 34).map((row) => `<tr><td>${formatDate(row.data)}</td><td>${row.jogos_previstos}</td><td>${row.jogos_validados}</td><td>${row.jogos_validados ? row["acuracia_vencedor_%"] + "%" : "—"}</td><td>${row.jogos_validados ? row["placar_exato_%"] + "%" : "—"}</td><td>${row.erro_medio_total_gols || "—"}</td></tr>`).join("");
    } else {
      predictions.forEach((row) => {
      if (!byDate.has(row.data)) byDate.set(row.data, { data: row.data, previstos: 0, validados: 0, vencedor: 0, exato: 0, erro: 0 });
      const item = byDate.get(row.data);
      item.previstos += 1;
      if (row.possui_real === "Sim" && row.placar_real) {
        item.validados += 1;
        const predWinner = row.vencedor_previsto || row.vencedor_rede_neural || scoreWinner(row.equipe1, row.equipe2, row.placar_previsto || row.placar_rede_neural);
        const realWinner = scoreWinner(row.equipe1, row.equipe2, row.placar_real);
        const predScore = row.placar_previsto || row.placar_rede_neural;
        if (predWinner === realWinner) item.vencedor += 1;
        if (predScore === row.placar_real) item.exato += 1;
        const ps = parseScore(predScore) || [0,0];
        const rs = parseScore(row.placar_real) || [0,0];
        item.erro += Math.abs(ps[0] - rs[0]) + Math.abs(ps[1] - rs[1]);
      }
    });
      const validRows = [...byDate.values()].slice(0, 22);
      daily.innerHTML = validRows.map((row) => `<tr><td>${formatDate(row.data)}</td><td>${row.previstos}</td><td>${row.validados}</td><td>${row.validados ? Math.round(row.vencedor / row.validados * 100) + "%" : "—"}</td><td>${row.validados ? Math.round(row.exato / row.validados * 100) + "%" : "—"}</td><td>${row.validados ? (row.erro / row.validados).toFixed(2) : "—"}</td></tr>`).join("");
    }
  }

  const predBody = document.getElementById("neural-predictions-body");
  if (predBody) {
    predBody.innerHTML = predictions.slice(0, 18).map((row) => `
      <tr>
        <td>${row.jogo}</td>
        <td>${phaseLabels[row.fase] || row.fase}</td>
        <td>${teamChip(row.equipe1)} x ${teamChip(row.equipe2)}</td>
        <td><b>${row.placar_previsto || row.placar_modelo_diario || row.placar_rede_neural || "—"}</b></td>
        <td>${row.vencedor_previsto || row.vencedor_modelo_diario || row.vencedor_rede_neural || "—"}</td>
        <td>${row.placar_real || "—"}</td>
      </tr>
    `).join("");
  }

  const teamGrid = document.getElementById("neural-team-grid");
  if (teamGrid) {
    const teamRows = modeloDiarioEstadoTimes.length ? modeloDiarioEstadoTimes : redeNeuralTeams;
    teamGrid.innerHTML = teamRows.slice(0, 12).map((row, index) => {
      const strength = Number(row.rating_atual_0_100 || row.forca_modelo_0_100 || 0);
      const league = Number(row.saldo ?? row.league_score_top11 ?? row.league_score_mean ?? 0).toFixed(1);
      const players = Number(row.memoria_desempenho ?? row.player_proxy_top18 ?? row.player_proxy_mean ?? 0).toFixed(1);
      return `<div class="neural-team"><b>${index + 1}</b><div>${teamChip(row.selecao)}<span>Rating ${strength.toFixed(1)} · Saldo ${league} · Memória ${players}</span><i style="width:${Math.max(0, Math.min(100, strength))}%"></i></div><strong>${strength.toFixed(1)}</strong></div>`;
    }).join("");
  }
}

function bindEvents() {
  document.getElementById("group-prev")?.addEventListener("click", () => { groupPage--; renderStandingsPage(); });
  document.getElementById("group-next")?.addEventListener("click", () => { groupPage++; renderStandingsPage(); });
  document.getElementById("group-games-prev")?.addEventListener("click", () => { groupGamesPage--; renderGroupGamesPage(); });
  document.getElementById("group-games-next")?.addEventListener("click", () => { groupGamesPage++; renderGroupGamesPage(); });
  document.getElementById("group-search")?.addEventListener("input", () => { groupGamesPage = 0; renderGroupGamesPage(); });
  document.getElementById("group-filter")?.addEventListener("change", () => { groupGamesPage = 0; renderGroupGamesPage(); });
  document.getElementById("ko-games-prev")?.addEventListener("click", () => { knockoutGamesPage--; renderKnockoutGamesPage(); });
  document.getElementById("ko-games-next")?.addEventListener("click", () => { knockoutGamesPage++; renderKnockoutGamesPage(); });
  document.getElementById("ko-phase-filter")?.addEventListener("change", () => { knockoutGamesPage = 0; renderKnockoutGamesPage(); });
  window.addEventListener("resize", () => {
    if (page === "groups-results") renderStandingsPage();
    if (page === "groups-games") renderGroupGamesPage();
    if (page === "knockout-games") renderKnockoutGamesPage();
    if (page === "knockout-bracket") fitBracket();
  });
}

function init() {
  buildMatches();
  renderCommonStats();
  bindEvents();
  if (page === "groups-results") { renderSummaryCards(); renderStandingsPage(); }
  if (page === "groups-games") { setupGroupFilter(); renderGroupGamesPage(); }
  if (page === "knockout-bracket") renderBracketPage();
  if (page === "knockout-games") { setupKoFilter(); renderKnockoutGamesPage(); }
  if (page === "neural-network") renderNeuralPage();
}

init();
