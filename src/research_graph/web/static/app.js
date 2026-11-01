"use strict";
const form = document.querySelector("#search-form");
const query = document.querySelector("#query");
const button = document.querySelector("#search-button");
const buttonLabel = document.querySelector("#button-label");
const topK = document.querySelector("#top-k");
const statusMessage = document.querySelector("#search-status");
const error = document.querySelector("#error");
const results = document.querySelector("#results");
const section = document.querySelector("#results-section");
const empty = document.querySelector("#empty-state");
const catalog = document.querySelector("#catalog-status");
const examples = {
  notebook:
    "Парень находит тетрадь, которая убивает людей, если записать в неё имя человека.",
  pirates:
    "Юный пират собирает команду, чтобы найти легендарное сокровище и стать королём пиратов. Они отправляются в опасное морское путешествие.",
  spirits:
    "Девочка попадает в мир духов и пытается спасти родителей, которые превратились в свиней.",
};
let pending = false;
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function displayError(message) {
  error.textContent = message;
  error.hidden = false;
}
function render(hits) {
  results.replaceChildren();
  hits.forEach((hit, index) => {
    const anime = hit.anime;
    const item = node("li", undefined, "result");
    const rank = node("span", String(index + 1).padStart(2, "0"), "rank");
    rank.setAttribute("aria-label", `Место ${index + 1}`);
    const body = node("div");
    const head = node("div", undefined, "result-head");
    head.append(
      node("h3", anime.title),
      node("span", `Сходство ${hit.score.toFixed(3)}`, "score"),
    );
    body.append(head);
    if (anime.genres) {
      const tags = node("div", undefined, "tags");
      anime.genres
        .split(",")
        .slice(0, 4)
        .forEach((genre) => tags.append(node("span", genre.trim(), "tag")));
      body.append(tags);
    }
    const synopsis = anime.synopsis || "Синопсис не указан.";
    body.append(
      node(
        "p",
        synopsis.length > 300 ? synopsis.slice(0, 300) + "…" : synopsis,
        "synopsis",
      ),
    );
    if (synopsis.length > 300) {
      const details = node("details");
      details.append(node("summary", "Полный синопсис"), node("p", synopsis));
      body.append(details);
    }
    body.append(
      node("p", "Синопсис из каталога · язык источника", "source-label"),
    );
    item.append(rank, body);
    results.append(item);
  });
  section.hidden = hits.length === 0;
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pending || !form.reportValidity()) return;
  const description = query.value.trim();
  if (description.length < 3) {
    displayError("Добавь хотя бы несколько деталей — нужно от 3 символов.");
    query.focus();
    return;
  }
  pending = true;
  form.setAttribute("aria-busy", "true");
  button.disabled = true;
  buttonLabel.textContent = "Ищем…";
  query.readOnly = true;
  document.querySelectorAll("[data-example]").forEach((item) => {
    item.disabled = true;
  });
  topK.disabled = true;
  error.hidden = true;
  section.hidden = true;
  empty.hidden = true;
  statusMessage.textContent =
    "Сравниваем описание с синопсисами в локальном каталоге…";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: description, top_k: Number(topK.value) }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.error || "Не удалось выполнить поиск.");
    if (!Array.isArray(data.results))
      throw new Error("Сервер вернул некорректный ответ.");
    render(data.results);
    statusMessage.textContent = data.results.length
      ? `Показано вариантов: ${data.results.length}. Попробуй уточнить описание, если нужного нет.`
      : "Подходящих записей в индексе не найдено.";
  } catch (failure) {
    statusMessage.textContent = "";
    displayError(
      failure.name === "AbortError"
        ? "Поиск занял слишком много времени. Попробуй ещё раз."
        : failure.message === "Failed to fetch"
          ? "Нет связи с локальным сервером. Проверь, что команда serve ещё работает."
          : failure.message,
    );
  } finally {
    clearTimeout(timer);
    pending = false;
    button.disabled = false;
    buttonLabel.textContent = "Найти аниме";
    query.readOnly = false;
    document.querySelectorAll("[data-example]").forEach((item) => {
      item.disabled = false;
    });
    topK.disabled = false;
    form.removeAttribute("aria-busy");
  }
});
document.querySelectorAll("[data-example]").forEach((item) =>
  item.addEventListener("click", () => {
    if (pending) return;
    query.value = examples[item.dataset.example];
    query.focus();
    form.requestSubmit();
  }),
);
query.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey))
    form.requestSubmit();
});
fetch("/api/health")
  .then(async (response) => {
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    catalog.textContent = `В индексе ${new Intl.NumberFormat("ru-RU").format(data.index.count)} аниме с описаниями`;
  })
  .catch(() => {
    catalog.textContent =
      "Каталог недоступен — проверь локальный сервер и индекс.";
  });
