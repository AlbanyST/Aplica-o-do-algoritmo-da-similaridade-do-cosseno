const searchInput = document.querySelector("#game-search");
const searchResults = document.querySelector("#search-results");
const recommendationGrid = document.querySelector("#recommendation-grid");
const selectedGameElement = document.querySelector("#selected-game");
const emptyState = document.querySelector("#empty-state");
const statusMessage = document.querySelector("#status-message");
const resultsTitle = document.querySelector("#results-title");
const resultsMeta = document.querySelector("#results-meta");
const formulaExplanation = document.querySelector("#formula-explanation");
const datasetCount = document.querySelector("#dataset-count");

let searchTimer;
let latestSearch = 0;
let latestSelection = 0;

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function formatPrice(price) {
  return price === 0
    ? "Gratuito"
    : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" }).format(price);
}

function makeImage(game, className) {
  const image = makeElement("img", className);
  image.src = game.image;
  image.alt = `Capa de ${game.name}`;
  image.loading = "lazy";
  image.addEventListener("error", () => {
    image.removeAttribute("src");
    image.alt = `Imagem indisponível: ${game.name}`;
  }, { once: true });
  return image;
}

function makeTagList(tags, selectedTags = null, limit = 5) {
  const list = makeElement("div", "tag-list");
  const shown = tags.slice(0, limit);
  for (const tag of shown) {
    const chip = makeElement("span", "tag-chip", tag);
    if (selectedTags?.has(tag)) chip.classList.add("shared");
    list.append(chip);
  }
  if (tags.length > limit) {
    list.append(makeElement("span", "tag-overflow", `+${tags.length - limit}`));
  }
  return list;
}

function renderSearchResults(games) {
  searchResults.replaceChildren();
  if (games.length === 0) {
    searchResults.append(makeElement("div", "search-empty", "Nenhum jogo encontrado. Tente outro título."));
  } else {
    for (const game of games) {
      const option = makeElement("button", "search-option");
      option.type = "button";
      option.setAttribute("role", "option");
      option.append(makeImage(game, ""));
      const details = makeElement("span");
      details.append(
        makeElement("span", "search-option-name", game.name),
        makeElement("span", "search-option-tags", game.tags.slice(0, 3).join(" · ")),
      );
      option.append(details);
      option.addEventListener("click", () => selectGame(game));
      searchResults.append(option);
    }
  }
  searchResults.hidden = false;
  searchInput.setAttribute("aria-expanded", "true");
}

async function searchGames(query) {
  const requestNumber = ++latestSearch;
  if (query.trim().length < 2) {
    searchResults.hidden = true;
    searchInput.setAttribute("aria-expanded", "false");
    return;
  }

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error("Não foi possível buscar jogos agora.");
    const data = await response.json();
    if (requestNumber === latestSearch) renderSearchResults(data.results);
  } catch (error) {
    if (requestNumber === latestSearch) showError(error.message);
  }
}

function renderSelectedGame(game) {
  selectedGameElement.replaceChildren();
  selectedGameElement.append(makeImage(game, "selected-image"));
  const details = makeElement("div", "selected-details");
  details.append(
    makeElement("p", "selected-label", "JOGO ESCOLHIDO · TAGS DA STEAM"),
    makeElement("h3", "", game.name),
    makeTagList(game.tags, null, 12),
  );
  selectedGameElement.append(details);
  selectedGameElement.hidden = false;
}

function renderRecommendation(game, selectedTags) {
  const card = makeElement("article", "game-card");
  const imageWrap = makeElement("div", "card-image-wrap");
  imageWrap.append(makeImage(game, "card-image"));

  const badge = makeElement("div", "similarity-badge");
  badge.append(
    makeElement("strong", "", `${game.similarity.toFixed(1)}%`),
    makeElement("span", "", "SIMILAR"),
  );
  imageWrap.append(badge);

  const content = makeElement("div", "card-content");
  const titleRow = makeElement("div", "card-title-row");
  titleRow.append(makeElement("h3", "", game.name));
  if (game.rating !== null) {
    const rating = makeElement("span", "game-rating");
    rating.append(makeElement("strong", "", `${game.rating}%`), document.createTextNode(" positivo"));
    titleRow.append(rating);
  }
  content.append(titleRow);
  content.append(makeElement("p", "card-shared", `${game.sharedCount} TAG${game.sharedCount === 1 ? "" : "S"} EM COMUM`));
  content.append(makeTagList(game.tags, selectedTags, 4));

  const footer = makeElement("div", "card-footer");
  footer.append(makeElement("span", "", formatPrice(game.price)));
  const steamLink = makeElement("a", "", "VER NA STEAM ↗");
  steamLink.href = `https://store.steampowered.com/app/${encodeURIComponent(game.id)}/`;
  steamLink.target = "_blank";
  steamLink.rel = "noreferrer";
  footer.append(steamLink);
  content.append(footer);
  card.append(imageWrap, content);
  return card;
}

function renderRecommendations(data) {
  recommendationGrid.replaceChildren();
  renderSelectedGame(data.selected);
  const selectedTags = new Set(data.selected.tags);
  for (const game of data.recommendations) {
    recommendationGrid.append(renderRecommendation(game, selectedTags));
  }

  const tags = data.selected.tags.length;
  const perfectMatchText = data.recommendations.length
    ? "A recomendação mais próxima aparece primeiro; jogos podem ter pontuação igual quando compartilham as mesmas tags."
    : "Este jogo não tem outras correspondências com tags na base.";
  resultsTitle.textContent = `Quem curte ${data.selected.name} também pode curtir`;
  resultsMeta.textContent = `${tags} TAG${tags === 1 ? "" : "S"} NO JOGO · ${data.recommendations.length} RECOMENDAÇÕES`;
  formulaExplanation.textContent = perfectMatchText;
  emptyState.hidden = true;
  statusMessage.hidden = true;
}

async function selectGame(game) {
  const requestNumber = ++latestSelection;
  searchInput.value = game.name;
  searchResults.hidden = true;
  searchInput.setAttribute("aria-expanded", "false");
  latestSearch++;
  recommendationGrid.replaceChildren();
  emptyState.hidden = true;
  statusMessage.hidden = true;
  selectedGameElement.hidden = true;
  resultsTitle.textContent = "Calculando similaridade...";
  resultsMeta.textContent = "";

  try {
    const response = await fetch(`/api/recommend?id=${encodeURIComponent(game.id)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Não foi possível calcular recomendações.");
    if (requestNumber !== latestSelection) return;
    renderRecommendations(data);
  } catch (error) {
    if (requestNumber === latestSelection) showError(error.message);
  }
}

function showError(message) {
  statusMessage.textContent = message;
  statusMessage.hidden = false;
}

searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => searchGames(searchInput.value), 200);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    searchResults.hidden = true;
    searchInput.setAttribute("aria-expanded", "false");
  }
  if (event.key === "Enter") {
    const firstResult = searchResults.querySelector(".search-option");
    if (firstResult && !searchResults.hidden) firstResult.click();
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".search-wrap")) {
    searchResults.hidden = true;
    searchInput.setAttribute("aria-expanded", "false");
  }
});

if (window.location.protocol === "file:") {
  datasetCount.textContent = "SERVIDOR NECESSÁRIO";
  searchInput.disabled = true;
  searchInput.placeholder = "Inicie o servidor para buscar jogos";
  document.querySelector(".search-hint").textContent =
    "Abra um terminal na pasta do projeto, execute python app.py e acesse http://127.0.0.1:8000.";
} else {
  fetch("/api/stats")
    .then((response) => {
      if (!response.ok) throw new Error("Erro ao carregar o catálogo.");
      return response.json();
    })
    .then((data) => {
      datasetCount.textContent = `${data.games.toLocaleString("pt-BR")} JOGOS · ${data.tags} TAGS`;
    })
    .catch(() => {
      datasetCount.textContent = "Catálogo indisponível";
      showError("Não foi possível carregar os dados. Confira se o servidor iniciou corretamente.");
    });
}
