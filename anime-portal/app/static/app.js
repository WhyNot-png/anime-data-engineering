"use strict";

const API = "/api/v1";
const state = { page: 1, size: 10, pages: 1, userId: null, genres: [], studios: [], editing: null, reviewAnime: null };

const $ = (selector) => document.querySelector(selector);
const alertBox = $("#alert");
const alertText = $("#alert-text");

function showError(message, code) {
  alertText.textContent = code ? `${message} (${code})` : message;
  alertBox.hidden = false;
}
function clearError() {
  alertBox.hidden = true;
}
$("#alert-close").addEventListener("click", clearError);

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const error = (data && data.error) || { message: `HTTP ${response.status}`, code: "http_error" };
    const details = Array.isArray(error.details)
      ? error.details.map((item) => `${item.field}: ${item.message}`).join("; ")
      : "";
    throw new Error(`${error.message}${details ? ` — ${details}` : ""}|${error.code}`);
  }
  return data;
}

function handle(error) {
  const [message, code] = String(error.message).split("|");
  showError(message, code);
}

/* ---------- справочники ---------- */
async function loadDictionaries() {
  const [genres, studios, users] = await Promise.all([
    api("/genres"),
    api("/studios?size=100"),
    api("/users?size=100"),
  ]);
  state.genres = genres;
  state.studios = studios.items;
  $("#f-genre").innerHTML =
    '<option value="">Все жанры</option>' +
    genres.map((genre) => `<option value="${genre.slug}">${genre.name}</option>`).join("");
  $("#a-genres").innerHTML = genres
    .map((genre) => `<option value="${genre.id}">${genre.name}</option>`)
    .join("");
  $("#a-studio").innerHTML =
    '<option value="">—</option>' +
    state.studios.map((studio) => `<option value="${studio.id}">${studio.name}</option>`).join("");
  const userSelect = $("#user-select");
  userSelect.innerHTML = users.items
    .map((user) => `<option value="${user.id}">${user.username}</option>`)
    .join("");
  state.userId = users.items.length ? users.items[0].id : null;
  userSelect.addEventListener("change", () => {
    state.userId = Number(userSelect.value);
    loadWatchlist();
  });
}

/* ---------- каталог ---------- */
function filtersQuery() {
  const params = new URLSearchParams();
  params.set("page", String(state.page));
  params.set("size", String(state.size));
  params.set("sort", $("#f-sort").value);
  const q = $("#f-q").value.trim();
  if (q) params.set("q", q);
  if ($("#f-genre").value) params.set("genre", $("#f-genre").value);
  if ($("#f-status").value) params.set("status", $("#f-status").value);
  if ($("#f-year-from").value) params.set("year_from", $("#f-year-from").value);
  if ($("#f-year-to").value) params.set("year_to", $("#f-year-to").value);
  return params.toString();
}

function animeRow(item) {
  const genres = item.genres.map((genre) => genre.name).join(", ") || "—";
  const rating = item.rating_avg === null ? "—" : `${item.rating_avg} (${item.reviews_count})`;
  return `<tr>
    <td><strong>${escapeHtml(item.title)}</strong><div class="muted">${escapeHtml(item.title_english || "")}</div></td>
    <td>${item.year ?? "—"}</td>
    <td>${item.episodes ?? "—"}</td>
    <td>${escapeHtml(item.studio ? item.studio.name : "—")}</td>
    <td class="muted">${escapeHtml(genres)}</td>
    <td>${rating}</td>
    <td class="actions">
      <button data-action="add" data-id="${item.id}">В список</button>
      <button data-action="review" data-id="${item.id}" data-title="${escapeAttr(item.title)}">Отзыв</button>
      <button data-action="edit" data-id="${item.id}">Изменить</button>
      <button data-action="delete" data-id="${item.id}" class="danger">Удалить</button>
    </td>
  </tr>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}
function escapeAttr(value) {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

async function loadCatalog() {
  try {
    clearError();
    const data = await api(`/anime?${filtersQuery()}`);
    state.pages = Math.max(data.pages, 1);
    $("#catalog-table tbody").innerHTML = data.items.length
      ? data.items.map(animeRow).join("")
      : '<tr><td colspan="7" class="muted">Ничего не найдено.</td></tr>';
    $("#catalog-status").textContent = `Найдено тайтлов: ${data.total}`;
    $("#page-info").textContent = `Страница ${data.page} из ${state.pages}`;
    $("#prev-page").disabled = data.page <= 1;
    $("#next-page").disabled = data.page >= state.pages;
  } catch (error) {
    handle(error);
  }
}

$("#filters").addEventListener("submit", (event) => {
  event.preventDefault();
  state.page = 1;
  loadCatalog();
});
$("#reset-filters").addEventListener("click", () => {
  $("#filters").reset();
  state.page = 1;
  loadCatalog();
});
$("#prev-page").addEventListener("click", () => {
  state.page = Math.max(1, state.page - 1);
  loadCatalog();
});
$("#next-page").addEventListener("click", () => {
  state.page = Math.min(state.pages, state.page + 1);
  loadCatalog();
});

$("#catalog-table").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  try {
    clearError();
    if (button.dataset.action === "add") {
      await api(`/users/${state.userId}/watchlist`, {
        method: "POST",
        body: JSON.stringify({ anime_id: id }),
      });
      await loadWatchlist();
      showInfo("Тайтл добавлен в список.");
    }
    if (button.dataset.action === "delete") {
      if (!confirm("Удалить тайтл?")) return;
      await api(`/anime/${id}`, { method: "DELETE" });
      await loadCatalog();
    }
    if (button.dataset.action === "edit") {
      await openAnimeDialog(id);
    }
    if (button.dataset.action === "review") {
      state.reviewAnime = { id, title: button.dataset.title };
      $("#review-anime-title").textContent = button.dataset.title;
      $("#review-form").reset();
      $("#review-dialog").showModal();
    }
  } catch (error) {
    handle(error);
  }
});

/* ---------- создание и редактирование ---------- */
async function openAnimeDialog(id = null) {
  state.editing = id;
  $("#dialog-title").textContent = id ? "Изменить тайтл" : "Новый тайтл";
  $("#anime-form").reset();
  if (id) {
    const item = await api(`/anime/${id}`);
    $("#a-title").value = item.title;
    $("#a-title-en").value = item.title_english || "";
    $("#a-synopsis").value = item.synopsis || "";
    $("#a-year").value = item.year || "";
    $("#a-episodes").value = item.episodes ?? "";
    $("#a-status").value = item.status;
    $("#a-studio").value = item.studio ? item.studio.id : "";
    Array.from($("#a-genres").options).forEach((option) => {
      option.selected = item.genres.some((genre) => genre.id === Number(option.value));
    });
  }
  $("#anime-dialog").showModal();
}

$("#new-anime").addEventListener("click", () => openAnimeDialog().catch(handle));
$("#cancel-anime").addEventListener("click", () => $("#anime-dialog").close());

$("#anime-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    title: $("#a-title").value.trim(),
    title_english: $("#a-title-en").value.trim() || null,
    synopsis: $("#a-synopsis").value.trim() || null,
    year: $("#a-year").value ? Number($("#a-year").value) : null,
    episodes: $("#a-episodes").value === "" ? null : Number($("#a-episodes").value),
    status: $("#a-status").value,
    studio_id: $("#a-studio").value ? Number($("#a-studio").value) : null,
    genre_ids: Array.from($("#a-genres").selectedOptions).map((option) => Number(option.value)),
  };
  try {
    clearError();
    if (state.editing) {
      await api(`/anime/${state.editing}`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await api("/anime", { method: "POST", body: JSON.stringify(payload) });
    }
    $("#anime-dialog").close();
    await loadCatalog();
  } catch (error) {
    handle(error);
  }
});

/* ---------- список просмотра ---------- */
async function loadWatchlist() {
  if (!state.userId) return;
  try {
    const params = new URLSearchParams({ size: "50" });
    if ($("#watch-filter").value) params.set("status", $("#watch-filter").value);
    const data = await api(`/users/${state.userId}/watchlist?${params}`);
    $("#watchlist-status").textContent = `Записей: ${data.total}`;
    $("#watchlist").innerHTML = data.items
      .map((entry) => {
        const total = entry.anime.episodes || 0;
        return `<li class="card">
          <div>
            <strong>${escapeHtml(entry.anime.title)}</strong>
            <div class="muted">${entry.status} · ${entry.progress}${total ? ` / ${total}` : ""} эп.</div>
          </div>
          <div class="actions">
            <button data-watch="progress" data-id="${entry.id}" data-progress="${entry.progress}">+1 эп.</button>
            <button data-watch="status" data-id="${entry.id}" data-status="dropped">Бросить</button>
            <button data-watch="delete" data-id="${entry.id}" class="danger">Убрать</button>
          </div>
        </li>`;
      })
      .join("");
  } catch (error) {
    handle(error);
  }
}

$("#watch-filter").addEventListener("change", loadWatchlist);

$("#watchlist").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-watch]");
  if (!button) return;
  const id = Number(button.dataset.id);
  try {
    clearError();
    if (button.dataset.watch === "progress") {
      await api(`/watchlist/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ progress: Number(button.dataset.progress) + 1 }),
      });
    }
    if (button.dataset.watch === "status") {
      await api(`/watchlist/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: button.dataset.status }),
      });
    }
    if (button.dataset.watch === "delete") {
      await api(`/watchlist/${id}`, { method: "DELETE" });
    }
    await loadWatchlist();
    await loadCatalog();
  } catch (error) {
    handle(error);
  }
});

/* ---------- отзыв ---------- */
$("#cancel-review").addEventListener("click", () => $("#review-dialog").close());
$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    clearError();
    await api(`/anime/${state.reviewAnime.id}/reviews?user_id=${state.userId}`, {
      method: "POST",
      body: JSON.stringify({
        rating: Number($("#r-rating").value),
        body: $("#r-body").value.trim() || null,
      }),
    });
    $("#review-dialog").close();
    await loadCatalog();
    showInfo("Отзыв сохранён.");
  } catch (error) {
    handle(error);
  }
});

function showInfo(message) {
  alertText.textContent = message;
  alertBox.hidden = false;
  alertBox.classList.add("info");
  setTimeout(() => alertBox.classList.remove("info"), 2500);
}

/* ---------- аналитика ---------- */
async function loadAnalytics() {
  try {
    const [top, genres, years] = await Promise.all([
      api("/analytics/top-anime?limit=5&min_reviews=1"),
      api("/analytics/genres?limit=8"),
      api("/analytics/years"),
    ]);
    $("#top-table tbody").innerHTML = top.length
      ? top
          .map(
            (item, index) =>
              `<tr><td>${index + 1}</td><td>${escapeHtml(item.title)}</td><td>${item.year ?? "—"}</td><td>${item.reviews_count}</td><td>${item.rating_avg}</td></tr>`,
          )
          .join("")
      : '<tr><td colspan="5" class="muted">Пока нет отзывов.</td></tr>';
    $("#genres-table tbody").innerHTML = genres
      .map(
        (item) =>
          `<tr><td>${escapeHtml(item.genre)}</td><td>${item.anime_count}</td><td>${item.avg_rating ?? "—"}</td></tr>`,
      )
      .join("");
    $("#years-table tbody").innerHTML = years
      .map(
        (item) =>
          `<tr><td>${item.year}</td><td>${item.titles}</td><td>${item.episodes_total ?? "—"}</td></tr>`,
      )
      .join("");
  } catch (error) {
    handle(error);
  }
}

/* ---------- вкладки ---------- */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
    tab.classList.add("is-active");
    document.querySelectorAll(".panel").forEach((panel) => (panel.hidden = true));
    $(`#panel-${tab.dataset.panel}`).hidden = false;
    clearError();
    if (tab.dataset.panel === "watchlist") loadWatchlist();
    if (tab.dataset.panel === "analytics") loadAnalytics();
  });
});

loadDictionaries()
  .then(() => Promise.all([loadCatalog(), loadWatchlist()]))
  .catch(handle);
