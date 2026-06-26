const data = window.WC2026_DATA;
const matches = data.matches;
const groups = data.groups;

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
  const [year, month, day] = dateISO.split("-");
  return `${day}/${month}/${year}`;
}

function fillStats() {
  document.getElementById("stat-total").textContent = data.summary.totalJogos;
  document.getElementById("stat-groups").textContent = data.summary.faseGrupos;
  document.getElementById("stat-ko").textContent = data.summary.mataMata;
  document.getElementById("stat-hosts").textContent = data.summary.sedes.length;
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.view;
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("is-active", tab === button));
      document.querySelectorAll(".view").forEach((section) => section.classList.remove("is-active"));
      document.getElementById(`${view}-view`).classList.add("is-active");
    });
  });
}

function setupFilters() {
  const groupSelect = document.getElementById("group-filter");
  groups.forEach((group) => {
    const option = document.createElement("option");
    option.value = group.grupo;
    option.textContent = `Grupo ${group.grupo}`;
    groupSelect.appendChild(option);
  });

  const koPhaseSelect = document.getElementById("ko-phase-filter");
  [...new Set(matches.filter((m) => m.fase !== "Fase de grupos").map((m) => m.fase))]
    .forEach((phase) => {
      const option = document.createElement("option");
      option.value = phase;
      option.textContent = phaseLabels[phase] || phase;
      koPhaseSelect.appendChild(option);
    });

  document.getElementById("group-search").addEventListener("input", renderGroupGames);
  groupSelect.addEventListener("change", renderGroupGames);
  koPhaseSelect.addEventListener("change", renderKnockoutList);
}

function renderGroupsGrid() {
  const container = document.getElementById("groups-grid");
  container.innerHTML = groups.map((group) => `
    <article class="group-card">
      <strong>Grupo ${group.grupo}</strong>
      <ul>
        ${group.equipes.map((team) => `<li>${team}</li>`).join("")}
      </ul>
    </article>
  `).join("");
}

function renderGroupGames() {
  const body = document.getElementById("group-games-body");
  const selectedGroup = document.getElementById("group-filter").value;
  const search = normalize(document.getElementById("group-search").value);

  const filtered = matches
    .filter((match) => match.fase === "Fase de grupos")
    .filter((match) => selectedGroup === "all" || match.grupo === selectedGroup)
    .filter((match) => {
      if (!search) return true;
      return normalize(`${match.equipe1} ${match.equipe2} ${match.estadio} ${match.cidade} ${match.pais}`).includes(search);
    });

  body.innerHTML = filtered.map((match) => `
    <tr>
      <td>${match.jogo}</td>
      <td>${formatDate(match.data)}<br><span class="muted">${match.diaSemana}</span></td>
      <td>${match.horaLocal}<br><span class="muted">${match.horaET} ET</span></td>
      <td>Grupo ${match.grupo}<br><span class="muted">Rodada ${match.rodadaGrupo}</span></td>
      <td class="match">${match.confronto}</td>
      <td>${match.estadio}</td>
      <td>${match.cidade}<br><span class="muted">${match.pais}</span></td>
    </tr>
  `).join("");
}

function renderMatchCard(match) {
  return `
    <article class="match-card">
      <div class="match-card__top">
        <span>Jogo ${match.jogo}</span>
        <span>${formatDate(match.data)} · ${match.horaLocal}</span>
      </div>
      <div class="match-card__teams">
        <span>${match.equipe1}</span>
        <span>${match.equipe2}</span>
      </div>
      <div class="match-card__meta">
        ${match.estadio}<br>
        ${match.cidade}, ${match.pais}
      </div>
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
      <section class="bracket-col">
        <h3>${round.title}</h3>
        ${roundMatches.map(renderMatchCard).join("")}
      </section>
    `;
  }).join("");
}

function renderKnockoutList() {
  const body = document.getElementById("ko-games-body");
  const selectedPhase = document.getElementById("ko-phase-filter").value;

  const filtered = matches
    .filter((match) => match.fase !== "Fase de grupos")
    .filter((match) => selectedPhase === "all" || match.fase === selectedPhase);

  body.innerHTML = filtered.map((match) => `
    <tr>
      <td>${match.jogo}</td>
      <td>${phaseLabels[match.fase] || match.fase}</td>
      <td>${formatDate(match.data)}<br><span class="muted">${match.diaSemana}</span></td>
      <td>${match.horaLocal}<br><span class="muted">${match.horaET} ET</span></td>
      <td class="match">${match.confronto}</td>
      <td>${match.estadio}</td>
      <td>${match.cidade}<br><span class="muted">${match.pais}</span></td>
    </tr>
  `).join("");
}

function init() {
  fillStats();
  setupTabs();
  setupFilters();
  renderGroupsGrid();
  renderGroupGames();
  renderBracket();
  renderKnockoutList();
}

document.addEventListener("DOMContentLoaded", init);
