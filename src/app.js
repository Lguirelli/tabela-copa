const baseData = window.WC2026_DATA;
const baseMatches = baseData.matches;
const groups = baseData.groups;
let matches = [...baseMatches];

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

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function formatDate(dateISO) {
  if (!dateISO) return "—";
  const [year, month, day] = dateISO.split("-");
  return `${day}/${month}/${year}`;
}

function isFinished(match) {
  const status = normalize(match.status);
  return Boolean(match.placar) || status.includes("final") || status.includes("encerr") || status.includes("complet");
}

function parseScore(score) {
  if (!score) return null;
  const clean = String(score).trim().replace(/\s/g, "");
  const found = clean.match(/^(\d+)(?:x|-|:)(\d+)$/i);
  if (!found) return null;
  return [Number(found[1]), Number(found[2])];
}

function splitLine(line) {
  return line.split(";").map((item) => item.trim());
}

function parseResultsText(text) {
  const rows = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!rows.length) return new Map();

  const header = splitLine(rows[0]).map(normalize);
  const index = Object.fromEntries(header.map((name, idx) => [name, idx]));
  const updates = new Map();

  rows.slice(1).forEach((line) => {
    const cols = splitLine(line);
    const gameNumber = Number(cols[index.jogo]);
    if (!gameNumber) return;

    updates.set(gameNumber, {
      status: cols[index.status] || "",
      placar: cols[index.placar] || "",
      equipe1: cols[index.equipe1] || "",
      equipe2: cols[index.equipe2] || "",
      vencedor: cols[index.vencedor] || ""
    });
  });

  return updates;
}

async function loadResults() {
  try {
    const response = await fetch(`./data/resultados.txt?v=${Date.now()}`);
    if (!response.ok) throw new Error("resultados.txt não encontrado");
    const text = await response.text();
    const updates = parseResultsText(text);

    matches = baseMatches.map((match) => {
      const update = updates.get(match.jogo);
      if (!update) return { ...match, placar: "", vencedor: "" };

      const equipe1 = update.equipe1 || match.equipe1;
      const equipe2 = update.equipe2 || match.equipe2;
      return {
        ...match,
        equipe1,
        equipe2,
        confronto: `${equipe1} x ${equipe2}`,
        status: update.status || match.status,
        placar: update.placar || "",
        vencedor: update.vencedor || ""
      };
    });
  } catch (error) {
    matches = baseMatches.map((match) => ({ ...match, placar: "", vencedor: "" }));
  }
}

function renderStats() {
  document.getElementById("stat-total").textContent = matches.length;
  document.getElementById("stat-groups").textContent = matches.filter((match) => match.fase === "Fase de grupos").length;
  document.getElementById("stat-ko").textContent = matches.filter((match) => match.fase !== "Fase de grupos").length;
  document.getElementById("stat-finished").textContent = matches.filter(isFinished).length;
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

  [...new Set(matches.filter((match) => match.fase !== "Fase de grupos").map((match) => match.fase))]
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
      const score = parseScore(match.placar);
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
                <td>${row.team}</td>
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

function renderStatus(status) {
  const label = status || "Agendado";
  const done = normalize(label).includes("final") || normalize(label).includes("encerr") || normalize(label).includes("complet");
  return `<span class="status ${done ? "status--done" : ""}">${label}</span>`;
}

function renderScore(match) {
  return match.placar ? `<strong class="score">${match.placar}</strong>` : `<span class="muted">—</span>`;
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
    <tr>
      <td>${match.jogo}</td>
      <td>${formatDate(match.data)}</td>
      <td>${match.horaLocal}</td>
      <td>${match.grupo}</td>
      <td><strong>${match.equipe1}</strong> x <strong>${match.equipe2}</strong></td>
      <td>${renderScore(match)}</td>
      <td>${renderStatus(match.status)}</td>
      <td>${match.estadio}</td>
      <td>${match.cidade}</td>
    </tr>
  `).join("");
}

function renderMatchCard(match) {
  return `
    <article class="match-card ${isFinished(match) ? "match-card--done" : ""}">
      <div class="match-card__top">
        <span>Jogo ${match.jogo}</span>
        <span>${phaseLabels[match.fase] || match.fase}</span>
      </div>
      <div class="match-card__teams">
        <span>${match.equipe1}</span>
        ${renderScore(match)}
        <span>${match.equipe2}</span>
      </div>
      ${match.vencedor ? `<div class="match-card__winner">Vencedor: ${match.vencedor}</div>` : ""}
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
    <tr>
      <td>${match.jogo}</td>
      <td>${phaseLabels[match.fase] || match.fase}</td>
      <td>${formatDate(match.data)}</td>
      <td>${match.horaLocal}</td>
      <td><strong>${match.equipe1}</strong> x <strong>${match.equipe2}</strong></td>
      <td>${renderScore(match)}</td>
      <td>${renderStatus(match.status)}</td>
      <td>${match.vencedor || "—"}</td>
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

async function init() {
  populateFilters();
  bindEvents();
  await loadResults();
  renderAll();
}

init();
