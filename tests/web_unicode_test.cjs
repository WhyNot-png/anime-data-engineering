// Execute the actual client handler with a minimal DOM and a stubbed API.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const listeners = {};
const elements = {};
for (const id of [
  "search-form", "query", "search-button", "button-label", "top-k",
  "search-status", "error", "results", "results-section", "empty-state", "catalog-status",
]) {
  elements[id] = {
    value: id === "top-k" ? "3" : "",
    textContent: "",
    hidden: false,
    addEventListener(type, callback) { listeners[`${id}:${type}`] = callback; },
    setAttribute() {},
    removeAttribute() {},
    reportValidity() { return true; },
    focus() {},
    replaceChildren() {},
  };
}
let posts = 0;
const document = {
  querySelector(selector) { return elements[selector.slice(1)]; },
  querySelectorAll() { return []; },
};
const fetch = async (url) => {
  if (url === "/api/search") {
    posts++;
    return {ok: true, json: async () => ({results: []})};
  }
  return {ok: true, json: async () => ({index: {count: 1}})};
};
const script = fs.readFileSync(
  path.join(__dirname, "../src/research_graph/web/static/app.js"), "utf8"
);
vm.runInNewContext(script, {
  document, fetch, AbortController, setTimeout, clearTimeout, Intl,
});

(async () => {
  for (const [length, shouldSend] of [[2, false], [3, true], [4000, true], [4001, false]]) {
    elements.query.value = "🔥".repeat(length);
    const previous = posts;
    await listeners["search-form:submit"]({preventDefault() {}});
    assert.equal(posts - previous, Number(shouldSend), `query length ${length}`);
    if (!shouldSend) assert.match(elements.error.textContent, /3 до 4000/);
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });