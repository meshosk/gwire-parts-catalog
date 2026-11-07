"use strict";

const $ = id => document.getElementById(id);
const kind = window.location.pathname === "/schemes" ? "schemes" : "parts";
const title = kind === "parts" ? "Parts" : "Schemes";
const file = new URLSearchParams(window.location.search).get("file");
const endpoint = `/api/${kind}${file !== null ? `?file=${encodeURIComponent(file)}` : ""}`;
let items = [], loaded = null, dirty = false, saving = false;
let availableTags = [], selectedTags = [];

$("page-title").textContent = title;
document.title = `${title} | Catalog manager`;
$("list-title").textContent = title;
$("back").href = `/${kind}`;
for (const link of document.querySelectorAll("nav a")) {
  if (link.getAttribute("href") === `/${kind}`) link.setAttribute("aria-current", "page");
}

function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}

async function request(url, data) {
  const response = await fetch(url, data === undefined ? undefined : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}

function renderList() {
  const query = $("search").value.trim().toLowerCase();
  const matches = items.filter(item => [item.name, item.description, item.file, ...item.tags]
    .some(value => value.toLowerCase().includes(query)));
  $("items").replaceChildren();
  $("count").textContent = `${matches.length} / ${items.length}`;
  $("empty").hidden = matches.length !== 0;
  for (const item of matches) {
    const row = document.createElement("li");
    const details = document.createElement("div");
    const link = document.createElement("a");
    link.href = `/${kind}?file=${encodeURIComponent(item.file)}`;
    link.textContent = item.name || item.file;
    const description = document.createElement("p");
    description.textContent = item.description;
    const tags = document.createElement("p");
    tags.className = "filename";
    tags.textContent = `${item.file}${item.tags.length ? ` · ${item.tags.join(", ")}` : ""}`;
    details.append(link, description, tags);
    row.append(details);
    $("items").append(row);
  }
}

function values() {
  return {
    name: $("name").value,
    description: $("description").value,
    tags: [...selectedTags]
  };
}

$("search").addEventListener("input", renderList);
function updateDirty() {
  if (!loaded || saving) return;
  dirty = JSON.stringify(values()) !== JSON.stringify({name: loaded.name, description: loaded.description, tags: loaded.tags});
  $("save").disabled = !dirty;
  status(dirty ? "You have unsaved changes." : "No unsaved changes.");
}

function closeTagOptions() {
  $("tag-options").hidden = true;
  $("tag-search").setAttribute("aria-expanded", "false");
}

function renderTagOptions() {
  const query = $("tag-search").value.trim().toLowerCase();
  const matches = availableTags.filter(tag => !selectedTags.includes(tag) && tag.includes(query));
  $("tag-options").replaceChildren();
  for (const tag of matches) {
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = tag;
    button.addEventListener("click", () => {
      if ($("fields").disabled || selectedTags.includes(tag)) return;
      selectedTags.push(tag);
      $("tag-search").value = "";
      renderSelectedTags();
      updateDirty();
      $("tag-search").focus();
      renderTagOptions();
    });
    row.append(button);
    $("tag-options").append(row);
  }
  $("tags-hint").textContent = matches.length
    ? "Choose a tag from the suggestions. Use arrow keys and Enter, or click."
    : "No available matching tags. New tags can be added on the Tags page.";
  $("tag-options").hidden = matches.length === 0;
  $("tag-search").setAttribute("aria-expanded", String(matches.length > 0));
}

function renderSelectedTags() {
  $("selected-tags").replaceChildren();
  for (const [index, tag] of selectedTags.entries()) {
    const chip = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = tag;
    if (!availableTags.includes(tag)) {
      chip.className = "unknown-tag";
      label.textContent += " (not in shared tags)";
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove tag: ${tag}`);
    remove.addEventListener("click", () => {
      if ($("fields").disabled) return;
      selectedTags.splice(index, 1);
      renderSelectedTags();
      updateDirty();
      $("tag-search").focus();
      renderTagOptions();
    });
    chip.append(label, remove);
    $("selected-tags").append(chip);
  }
}

$("name").addEventListener("input", updateDirty);
$("description").addEventListener("input", updateDirty);
$("tag-search").addEventListener("input", renderTagOptions);
$("tag-search").addEventListener("focus", renderTagOptions);
$("tag-search").addEventListener("keydown", event => {
  if (event.key === "Escape") closeTagOptions();
  if (event.key === "ArrowDown" || event.key === "Enter") {
    event.preventDefault();
    renderTagOptions();
    const first = $("tag-options").querySelector("button");
    if (first && event.key === "ArrowDown") first.focus();
    if (first && event.key === "Enter" && $("tag-search").value.trim()) first.click();
  }
});
$("tag-options").addEventListener("keydown", event => {
  const buttons = [...$("tag-options").querySelectorAll("button")];
  const index = buttons.indexOf(document.activeElement);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const next = index + (event.key === "ArrowDown" ? 1 : -1);
    if (next < 0) $("tag-search").focus();
    else buttons[Math.min(next, buttons.length - 1)]?.focus();
  }
  if (event.key === "Escape") {
    $("tag-search").focus();
    closeTagOptions();
  }
});
document.addEventListener("click", event => {
  if (!$("tag-picker").contains(event.target)) closeTagOptions();
});
$("tag-picker").addEventListener("focusout", event => {
  if (!$("tag-picker").contains(event.relatedTarget)) closeTagOptions();
});
$("metadata-editor").addEventListener("submit", async event => {
  event.preventDefault();
  if (!loaded || saving || !dirty) return;
  saving = true;
  closeTagOptions();
  $("fields").disabled = true;
  status("Saving changes…");
  try {
    loaded = await request(endpoint, {...values(), revision: loaded.revision});
    dirty = false;
    $("name").value = loaded.name;
    $("description").value = loaded.description;
    selectedTags = [...loaded.tags];
    renderSelectedTags();
    status("Metadata saved. Rebuild indexes to update catalog listings.");
  } catch (error) {
    status(error.message, true);
  } finally {
    saving = false;
    $("fields").disabled = false;
    $("save").disabled = !dirty;
  }
});
window.addEventListener("beforeunload", event => {
  if (dirty) { event.preventDefault(); event.returnValue = ""; }
});
$("build-indexes").addEventListener("click", async () => {
  if ($("build-indexes").disabled) return;
  // Rebuild can rename the file currently open in the editor.
  if (dirty || saving) { status("Save your metadata changes before rebuilding indexes.", true); return; }
  $("build-indexes").disabled = true;
  $("fields").disabled = true;
  $("index-status").textContent = "Rebuilding catalog indexes…";
  $("index-status").classList.toggle("error", false);
  try {
    const result = await request("/api/indexes", {});
    $("index-status").textContent = `Indexes rebuilt: ${result.parts} parts, ${result.schemes} schemes.`;
    if (file !== null) {
      // Return to the fresh list because rebuilds normalize filenames.
      $("fields").disabled = true;
      loaded = null;
      status("Indexes rebuilt. Return to the list to continue editing.");
    } else {
      items = (await request(endpoint)).items;
      renderList();
    }
  } catch (error) {
    $("index-status").textContent = error.message;
    $("index-status").classList.toggle("error", true);
  } finally {
    $("build-indexes").disabled = false;
    $("fields").disabled = loaded === null;
  }
});

if (file !== null) {
  $("list-section").hidden = true;
  $("edit-section").hidden = false;
  $("filename").textContent = file;
}
Promise.all([request(endpoint), file !== null ? request("/api/tags") : Promise.resolve(null)]).then(([data, vocabulary]) => {
  if (file !== null) {
    loaded = data;
    $("name").value = data.name;
    $("description").value = data.description;
    availableTags = vocabulary.tags;
    selectedTags = [...data.tags];
    renderSelectedTags();
    $("fields").disabled = false;
    status("Metadata loaded.");
  } else {
    items = data.items;
    $("search").disabled = false;
    renderList();
    status(`${title} loaded.`);
  }
}).catch(error => status(error.message, true));
