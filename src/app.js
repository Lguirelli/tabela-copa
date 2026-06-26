const baseData = window.WC2026_DATA;
const baseMatches = baseData.matches;
const groups = baseData.groups;
const predictions = window.WC2026_PREDICTIONS || [];
const realResults = window.WC2026_REAL_RESULTS || [];
const corrections = window.WC2026_CORRECTIONS || [];
const modelMetrics = window.WC2026_MODEL_METRICS || {};
const teamColors = window.WC2026_TEAM_COLORS || {};

let matches = [];

const phaseLabels = {
  "16 avos de final": "16 avos",
  "Oitavas de final": "Oitavas",
  "Quartas de final": "Quartas",
  "Semifinais": "Semifinais",
  "Disputa de 3º lugar": "3º lugar",
  "Final": "Final"
};

const bracketRounds = [
  { title: "16 avos", phases: ["16 avos de final"] },
  { title: "Oitavas", phases: ["Oitavas de final"] },
  { title: "Quartas", phases: ["Quartas de final"] },
  { title: "Semifinais", phases: ["Semifinais"] },
  { title: "Final e 3º lugar", phases: ["Final", "Disputa de 3º lugar"] }
];

const predictionByGame = new Map(predictions.map((item) => [Number(item.jogo), item]));
const realByGame = new Map(realResults.map((item) => [Number(item.jogo), item]));
const correctionByGame = new Map(corrections.map((item) => [Number(item.jogo), item]));

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

function getTeamColors(team) {
  const direct = teamColors[team];
  if (direct) return direct;
  const key = colorKey(team);
  const foundName = Object.keys(teamColors).find((name) => colorKey(name) === key);
  return foundName ? teamColors[foundName] : null;
}

function textColorFor(hex) {
  if (!hex || !/^#[0-9A-Fa-f]{6}$/.test(hex)) return "#ffffff";
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq >= 160 ? "#07101d" : "#ffffff";
}

function teamChip(team, side = "left") {
  if (!team || /^([123]º|Vencedor|Perdedor)/.test(team)) return `<span class="team-chip team-chip--slot">${team || "—"}</span>`;
  const colors = getTeamColors(team);
  if (!colors) return `<span class="team-chip">${team}</span>`;
  const primary = colors.primary || "#38bdf8";
  const secondary = colors.secondary || primary;
  const accent = colors.accent || secondary;
  const text = textColorFor(primary);
  return `<span class="team-chip team-chip--${side}" style="--team-primary:${primary};--team-secondary:${secondary};--team-accent:${accent};--team-text:${text};"><i aria-hidden="true"></i>${team}</span>`;
}

function matchAccentStyle(match) {
  const c1 = getTeamColors(match.equipe1);
  const c2 = getTeamColors(match.equipe2);
  const p1 = c1?.primary || "rgba(56,189,248,.7)";
  const p2 = c2?.primary || "rgba(132,204,22,.7)";
  return `style="--team-a:${p1};--team-b:${p2};"`;
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

function winnerFromScore(team1, team2, score) {
  const parsed = parseScore(score);
  if (!parsed) return "";
  const [g1, g2] = parsed;
  if (g1 > g2) return team1;
  if (g2 > g1) return team2;
  return "Empate";
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

function isFinished(match) {
  return Boolean(match.hasReal);
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

function renderMatchCard(match) {
  return `
    <article class="match-card ${isFinished(match) ? "match-card--done" : ""}" ${matchAccentStyle(match)}>
      <div class="match-card__top">
        <span>Jogo ${match.jogo}</span>
        <span>${phaseLabels[match.fase] || match.fase}</span>
      </div>
      <div class="match-card__teams">
        <span>${teamChip(match.equipe1, "left")}</span>
        <div class="score-stack">
          <small>Prev.</small>${renderScore(match.predictionScore, "prediction")}
          <small>Real</small>${match.hasReal ? renderScore(match.realScore, "real") : `<span class="muted">—</span>`}
        </div>
        <span>${teamChip(match.equipe2, "right")}</span>
      </div>
      ${match.hasReal ? `<div class="match-card__winner">Real: ${match.realWinner} · ${renderCorrection(match)}</div>` : `<div class="match-card__winner">Status: simulação · Previsto: ${match.predictionWinner || "—"}</div>`}
      <div class="match-card__meta">${formatDate(match.data)} · ${match.horaLocal} · ${match.cidade}</div>
    </article>
  `;
}

function renderBracket() {
  const container = document.getElementById("bracket");
  container.innerHTML = bracketRounds.map((round) => {
    const roundMatches = matches
      .filter((match) => round.phases.includes(match.fase))
      .sort((a, b) => a.jogo - b.jogo);

    return `
      <section class="bracket-round">
        <h3>${round.title}</h3>
        <div class="bracket-stack">
          ${roundMatches.map(renderMatchCard).join("")}
        </div>
      </section>
    `;
  }).join("");
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
    });
  });

  document.getElementById("group-search").addEventListener("input", renderGroupGames);
  document.getElementById("group-filter").addEventListener("change", () => {
    renderStandings();
    renderGroupGames();
  });
  document.getElementById("ko-phase-filter").addEventListener("change", renderKnockoutTable);
}

function init() {
  buildMatches();
  populateFilters();
  bindEvents();
  renderAll();
}

init();
