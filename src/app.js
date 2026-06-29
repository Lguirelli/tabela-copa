
const baseData = window.WC2026_DATA;
const baseMatches = baseData.matches;
const groups = baseData.groups;
const predictions = window.WC2026_PREDICTIONS || [];
const realResults = window.WC2026_REAL_RESULTS || [];
const corrections = window.WC2026_CORRECTIONS || [];
const modelMetrics = window.WC2026_MODEL_METRICS || {};
const teamColors = window.WC2026_TEAM_COLORS || {};
const teamAssets = window.WC2026_TEAM_ASSETS || {};

let matches = [];

const phaseLabels = {
  "16 avos de final": "16 avos",
  "Oitavas de final": "Oitavas",
  "Quartas de final": "Quartas",
  "Semifinais": "Semifinais",
  "Disputa de 3º lugar": "3º lugar",
  "Final": "Final"
};

const predictionByGame = new Map(predictions.map((item) => [Number(item.jogo), item]));
const realByGame = new Map(realResults.map((item) => [Number(item.jogo), item]));
const correctionByGame = new Map(corrections.map((item) => [Number(item.jogo), item]));

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
  center: {
    final: 104,
    third: 103
  }
};

const bracketConnections = [
  [73, 89], [75, 89], [74, 90], [77, 90], [89, 97], [90, 97],
  [83, 93], [84, 93], [81, 94], [82, 94], [93, 98], [94, 98],
  [97, 101], [98, 101],
  [76, 91], [78, 91], [79, 92], [80, 92], [91, 99], [92, 99],
  [85, 96], [87, 96], [86, 95], [88, 95], [95, 100], [96, 100],
  [99, 102], [100, 102],
  [101, 104], [102, 104],
  [101, 103], [102, 103]
];

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function colorKey(value) {
  return normalize(value)
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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

function getTeamColors(team) {
  const direct = teamColors[team];
  if (direct) return direct;
  const key = colorKey(team);
  const foundName = Object.keys(teamColors).find((name) => colorKey(name) === key);
  if (foundName) return teamColors[foundName];
  const asset = getTeamAsset(team);
  if (asset?.palette?.length) {
    const usable = asset.palette.filter((color) => /^#[0-9A-Fa-f]{6}$/.test(color));
    return {
      code: asset.code || "",
      primary: usable[0] || "#38bdf8",
      secondary: usable[1] || usable[0] || "#38bdf8",
      accent: usable[2] || usable[1] || usable[0] || "#38bdf8",
      palette: usable
    };
  }
  return null;
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

  return `
    <span class="team-chip team-chip--${side}" title="${safeAttr(team)}">
      ${icon}
      <span class="team-chip__name">${team}</span>
    </span>
  `;
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
  if (!found) return null;
  return [Number(found[1]), Number(found[2])];
}

function buildMatches() {
  matches = baseMatches.map((base) => {
    const prediction = predictionByGame.get(Number(base.jogo));
    const real = realByGame.get(Number(base.jogo));
    const correction = correctionByGame.get(Number(base.jogo));
    const hasReal = Boolean(real && real.placar_real);

    const equipe1 = hasReal
      ? real.equipe1
      : prediction?.equipe1_prevista || base.equipe1;
    const equipe2 = hasReal
      ? real.equipe2
      : prediction?.equipe2_prevista || base.equipe2;

    const predictionScore = hasReal
      ? prediction?.placar_previsto_original
      : prediction?.placar_previsto_atual || prediction?.placar_previsto_original;

    const predictionWinner = hasReal
      ? prediction?.vencedor_previsto_original
      : prediction?.vencedor_previsto_atual || prediction?.vencedor_previsto_original;

    return {
      ...base,
      equipe1,
      equipe2,
      confronto: `${equipe1} x ${equipe2}`,
      prediction,
      real,
      correction,
      hasReal,
      predictionScore: predictionScore || "",
      predictionWinner: predictionWinner || "",
      realScore: hasReal ? real.placar_real : "",
      realWinner: hasReal ? real.vencedor_real : "",
      status: hasReal ? "Finalizado" : "Simulação",
      scoreForTable: hasReal ? real.placar_real : (predictionScore || "")
    };
  });
}

function matchByGame(game) {
  return matches.find((item) => Number(item.jogo) === Number(game));
}

function renderStats() {
  const finished = matches.filter((match) => match.hasReal).length;
  document.getElementById("stat-total").textContent = matches.length;
  document.getElementById("stat-finished").textContent = finished;
  document.getElementById("stat-simulated").textContent = matches.length - finished;
  document.getElementById("stat-proximity").textContent = modelMetrics.proximidade_media_0_100
    ? `${modelMetrics.proximidade_media_0_100}%`
    : "—";
}

function populateFilters() {
  const groupFilter = document.getElementById("group-filter");
  const koPhaseFilter = document.getElementById("ko-phase-filter");

  groups.forEach((group) => {
    const option = document.createElement("option");
    option.value = group.grupo;
    option.textContent = `Grupo ${group.grupo}`;
    groupFilter.appendChild(option);
  });

  [...new Set(baseMatches.filter((match) => match.fase !== "Fase de grupos").map((match) => match.fase))]
    .forEach((phase) => {
      const option = document.createElement("option");
      option.value = phase;
      option.textContent = phaseLabels[phase] || phase;
      koPhaseFilter.appendChild(option);
    });
}

function initialStandingRows(group) {
  return Object.fromEntries(group.equipes.map((team) => [team, {
    team,
    played: 0,
    wins: 0,
    draws: 0,
    losses: 0,
    gf: 0,
    ga: 0,
    gd: 0,
    pts: 0
  }]));
}

function calculateStandings(group) {
  const table = initialStandingRows(group);
  matches
    .filter((match) => match.fase === "Fase de grupos" && match.grupo === group.grupo)
    .forEach((match) => {
      const score = parseScore(match.scoreForTable);
      if (!score) return;

      const [g1, g2] = score;
      if (!table[match.equipe1] || !table[match.equipe2]) return;

      const home = table[match.equipe1];
      const away = table[match.equipe2];
      home.played += 1;
      away.played += 1;
      home.gf += g1;
      home.ga += g2;
      away.gf += g2;
      away.ga += g1;

      if (g1 > g2) {
        home.wins += 1;
        away.losses += 1;
        home.pts += 3;
      } else if (g2 > g1) {
        away.wins += 1;
        home.losses += 1;
        away.pts += 3;
      } else {
        home.draws += 1;
        away.draws += 1;
        home.pts += 1;
        away.pts += 1;
      }
    });

  return Object.values(table)
    .map((row) => ({ ...row, gd: row.gf - row.ga }))
    .sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || a.team.localeCompare(b.team, "pt-BR"));
}

function renderStandings() {
  const container = document.getElementById("standings-grid");
  const selectedGroup = document.getElementById("group-filter").value;
  const visibleGroups = selectedGroup === "all" ? groups : groups.filter((group) => group.grupo === selectedGroup);

  container.innerHTML = visibleGroups.map((group) => {
    const rows = calculateStandings(group);
    return `
      <article class="standing-card">
        <h3>Grupo ${group.grupo}</h3>
        <table>
          <thead>
            <tr><th>#</th><th>Seleção</th><th>Pts</th><th>J</th><th>V</th><th>E</th><th>D</th><th>SG</th></tr>
          </thead>
          <tbody>
            ${rows.map((row, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${teamChip(row.team)}</td>
                <td>${row.pts}</td>
                <td>${row.played}</td>
                <td>${row.wins}</td>
                <td>${row.draws}</td>
                <td>${row.losses}</td>
                <td>${row.gd > 0 ? "+" : ""}${row.gd}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </article>
    `;
  }).join("");
}

function renderStatus(match) {
  const done = match.hasReal;
  return `<span class="status ${done ? "status--done" : "status--sim"}">${done ? "Finalizado" : "Simulação"}</span>`;
}

function renderScore(score, type = "prediction") {
  if (!score) return `<span class="muted">—</span>`;
  return `<strong class="score score--${type}">${score}</strong>`;
}

function renderCorrection(match) {
  if (!match.hasReal || !match.correction) return `<span class="muted">—</span>`;
  const ok = match.correction.acertou_vencedor === "Sim";
  return `
    <span class="correction ${ok ? "correction--ok" : "correction--miss"}">
      ${match.correction.proximidade_0_100}% · erro ${match.correction.erro_total_gols}
    </span>
  `;
}

function renderGroupGames() {
  const body = document.getElementById("group-games-body");
  const selectedGroup = document.getElementById("group-filter").value;
  const query = normalize(document.getElementById("group-search").value);

  const filtered = matches
    .filter((match) => match.fase === "Fase de grupos")
    .filter((match) => selectedGroup === "all" || match.grupo === selectedGroup)
    .filter((match) => {
      if (!query) return true;
      return normalize(`${match.equipe1} ${match.equipe2} ${match.estadio} ${match.cidade}`).includes(query);
    });

  body.innerHTML = filtered.map((match) => `
    <tr class="${match.hasReal ? "row-real" : "row-sim"}">
      <td>${match.jogo}</td>
      <td>${formatDate(match.data)}</td>
      <td>${match.horaLocal}</td>
      <td>${match.grupo}</td>
      <td><div class="versus-line">${teamChip(match.equipe1, "left")}<span>x</span>${teamChip(match.equipe2, "right")}</div></td>
      <td>${renderScore(match.predictionScore, "prediction")}</td>
      <td>${match.hasReal ? renderScore(match.realScore, "real") : `<span class="muted">—</span>`}</td>
      <td>${renderStatus(match)}</td>
      <td>${renderCorrection(match)}</td>
      <td>${match.estadio}</td>
      <td>${match.cidade}</td>
    </tr>
  `).join("");
}

function renderBracketCard(match, extraClass = "") {
  if (!match) return "";
  const displayScore = match.hasReal ? match.realScore : match.predictionScore;
  const displayType = match.hasReal ? "real" : "prediction";
  const secondaryLabel = match.hasReal ? "Rede neural" : "Real";
  const secondaryValue = match.hasReal ? (match.predictionScore || "—") : "—";
  return `
    <article class="bracket-card ${match.hasReal ? "bracket-card--done" : ""} ${extraClass}" data-game="${match.jogo}">
      <div class="bracket-card__meta">
        <span>Jogo ${match.jogo}</span>
        <span>${phaseLabels[match.fase] || match.fase}</span>
      </div>
      <div class="bracket-card__teams">
        <div class="bracket-team">${teamChip(match.equipe1, "left")}</div>
        <div class="bracket-card__score">${renderScore(displayScore, displayType)}</div>
        <div class="bracket-team bracket-team--right">${teamChip(match.equipe2, "right")}</div>
      </div>
      <div class="bracket-card__resultline">
        <span class="label">${secondaryLabel}</span>
        <span class="value">${secondaryValue}</span>
        <span class="bracket-card__status ${match.hasReal ? "is-real" : "is-sim"}">${match.hasReal ? "Finalizado" : "Simulação"}</span>
      </div>
      <div class="bracket-card__winner">${match.hasReal ? `Vencedor real: ${match.realWinner}` : `Previsto: ${match.predictionWinner || "—"}`}</div>
    </article>
  `;
}

function makeBracketSlots(games, column, rows, side) {
  return games.map((game, index) => {
    const match = matchByGame(game);
    const row = rows[index];
    return `
      <div class="bracket-slot" style="grid-column:${column}; grid-row:${row};">
        ${renderBracketCard(match, side === "right" ? "bracket-card--right" : "")}
      </div>
    `;
  }).join("");
}

function renderBracket() {
  const container = document.getElementById("bracket");
  const html = `
    <div class="bracket-frame">
      <div id="bracket-board" class="bracket-board">
        <svg class="bracket-svg" aria-hidden="true"></svg>

        ${makeBracketSlots(bracketLayout.left.r32, 1, [1,3,5,7,9,11,13,15], "left")}
        ${makeBracketSlots(bracketLayout.left.r16, 2, [2,6,10,14], "left")}
        ${makeBracketSlots(bracketLayout.left.qf, 3, [4,12], "left")}
        ${makeBracketSlots(bracketLayout.left.sf, 4, [8], "left")}

        <div class="bracket-slot bracket-slot--center" style="grid-column:5; grid-row:7 / span 2;">
          ${renderBracketCard(matchByGame(bracketLayout.center.final), "bracket-card--center")}
        </div>
        <div class="bracket-slot bracket-slot--third" style="grid-column:5; grid-row:11 / span 2;">
          ${renderBracketCard(matchByGame(bracketLayout.center.third), "bracket-card--third")}
        </div>

        ${makeBracketSlots(bracketLayout.right.sf, 6, [8], "right")}
        ${makeBracketSlots(bracketLayout.right.qf, 7, [4,12], "right")}
        ${makeBracketSlots(bracketLayout.right.r16, 8, [2,6,10,14], "right")}
        ${makeBracketSlots(bracketLayout.right.r32, 9, [1,3,5,7,9,11,13,15], "right")}
      </div>
    </div>
  `;
  container.innerHTML = html;
  requestAnimationFrame(drawBracketLines);
}

function drawBracketLines() {
  const board = document.getElementById("bracket-board");
  if (!board) return;
  const svg = board.querySelector(".bracket-svg");
  if (!svg) return;

  const boardRect = board.getBoundingClientRect();
  const width = board.scrollWidth;
  const height = board.scrollHeight;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.innerHTML = "";

  bracketConnections.forEach(([fromGame, toGame]) => {
    const fromCard = board.querySelector(`[data-game="${fromGame}"]`);
    const toCard = board.querySelector(`[data-game="${toGame}"]`);
    if (!fromCard || !toCard) return;

    const fromRect = fromCard.getBoundingClientRect();
    const toRect = toCard.getBoundingClientRect();

    const fromCenterY = fromRect.top - boardRect.top + fromRect.height / 2 + board.scrollTop;
    const toCenterY = toRect.top - boardRect.top + toRect.height / 2 + board.scrollTop;
    const fromIsLeft = fromRect.left < toRect.left;

    const startX = fromIsLeft
      ? (fromRect.right - boardRect.left + board.scrollLeft)
      : (fromRect.left - boardRect.left + board.scrollLeft);
    const endX = fromIsLeft
      ? (toRect.left - boardRect.left + board.scrollLeft)
      : (toRect.right - boardRect.left + board.scrollLeft);

    const elbowX = fromIsLeft
      ? startX + Math.max(24, (endX - startX) * 0.45)
      : startX - Math.max(24, (startX - endX) * 0.45);

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${startX} ${fromCenterY} L ${elbowX} ${fromCenterY} L ${elbowX} ${toCenterY} L ${endX} ${toCenterY}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", toGame === 103 ? "rgba(96,165,250,.65)" : "rgba(239,68,68,.65)");
    path.setAttribute("stroke-width", toGame === 104 ? "3" : "2.4");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);
  });
}

function renderKnockoutTable() {
  const body = document.getElementById("ko-games-body");
  const selectedPhase = document.getElementById("ko-phase-filter").value;
  const filtered = matches
    .filter((match) => match.fase !== "Fase de grupos")
    .filter((match) => selectedPhase === "all" || match.fase === selectedPhase);

  body.innerHTML = filtered.map((match) => `
    <tr class="${match.hasReal ? "row-real" : "row-sim"}">
      <td>${match.jogo}</td>
      <td>${phaseLabels[match.fase] || match.fase}</td>
      <td>${formatDate(match.data)}</td>
      <td>${match.horaLocal}</td>
      <td><div class="versus-line">${teamChip(match.equipe1, "left")}<span>x</span>${teamChip(match.equipe2, "right")}</div></td>
      <td>${renderScore(match.predictionScore, "prediction")}</td>
      <td>${match.hasReal ? renderScore(match.realScore, "real") : `<span class="muted">—</span>`}</td>
      <td>${renderStatus(match)}</td>
      <td>${match.hasReal ? match.realWinner : match.predictionWinner || "—"}</td>
      <td>${renderCorrection(match)}</td>
      <td>${match.estadio}</td>
      <td>${match.cidade}</td>
    </tr>
  `).join("");
}

function renderAll() {
  renderStats();
  renderStandings();
  renderGroupGames();
  renderBracket();
  renderKnockoutTable();
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("is-active"));
      tab.classList.add("is-active");
      document.getElementById(`${tab.dataset.view}-view`).classList.add("is-active");
      if (tab.dataset.view === "knockout") {
        setTimeout(drawBracketLines, 40);
      }
    });
  });

  document.getElementById("group-search").addEventListener("input", renderGroupGames);
  document.getElementById("group-filter").addEventListener("change", () => {
    renderStandings();
    renderGroupGames();
  });
  document.getElementById("ko-phase-filter").addEventListener("change", renderKnockoutTable);
  window.addEventListener("resize", () => {
    if (document.getElementById("knockout-view").classList.contains("is-active")) {
      drawBracketLines();
    }
  });
}

function init() {
  buildMatches();
  populateFilters();
  bindEvents();
  renderAll();
}

init();
