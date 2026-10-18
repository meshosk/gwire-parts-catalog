"use strict";

const normalize = value => value.trim().toLowerCase();

function distance(a, b) {
  let previous = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) {
      row[j] = Math.min(row[j - 1] + 1, previous[j] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    previous = row;
  }
  return previous[b.length];
}

function matchScore(tag, query) {
  if (!query || tag.includes(query)) return 0;
  const words = tag.split(/\s+/);
  const queries = query.split(/\s+/);
  const scores = queries.map(term => {
    const best = Math.min(...[tag, ...words].map(word => word.includes(term) ? 0 : distance(term, word)));
    return best <= Math.max(1, Math.floor(term.length * 0.3)) ? best : Infinity;
  });
  return scores.reduce((a, b) => a + b, 0);
}

// Also export the exact search used by the browser for dependency-free tests.
if (typeof module !== "undefined") module.exports = {normalize, distance, matchScore};

if (typeof document !== "undefined") {
  const $ = id => document.getElementById(id);
  let tags = [], revision = null, editing = null, dirty = false, saving = false;

  function status(message, error = false) {
    $("status").textContent = message;
    $("status").classList.toggle("error", error);
  }

  function changed() {
    dirty = true;
    status("You have unsaved changes.");
    render();
  }

  function resetEditor() {
    editing = null;
    $("editor").reset();
    $("edit-section").hidden = true;
    $("form-error").textContent = "";
  }

  function render() {
    $("save").disabled = !dirty || saving;
    $("tag").disabled = saving;
    $("submit-tag").disabled = saving || revision === null;
    $("cancel").disabled = saving;
    const query = normalize($("search").value);
    const exists = tags.includes(query);
    $("search").disabled = saving || revision === null;
    $("add-tag").disabled = saving || revision === null || !query || exists;
    $("search-hint").textContent = !query ? "Type to search, including similar spellings."
      : exists ? "This tag already exists."
      : `Press Enter or click Add tag to add “${query}”.`;
    const matches = tags.map(tag => ({tag, score: matchScore(tag, query)}))
      .filter(item => Number.isFinite(item.score)).sort((a, b) => a.score - b.score);
    $("count").textContent = `${matches.length} / ${tags.length}`;
    $("empty").hidden = matches.length !== 0;
    $("tags").replaceChildren();
    for (const {tag} of matches) {
      const row = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = tag;
      const actions = document.createElement("div");
      actions.className = "actions";
      for (const [text, className, action] of [
        ["Edit", "secondary", () => {
          editing = tag;
          $("tag").value = tag;
          $("editor-title").textContent = "Edit tag";
          $("submit-tag").textContent = "Apply";
          $("edit-section").hidden = false;
          $("form-error").textContent = "";
          $("tag").focus();
        }],
        ["Delete", "danger", () => {
          tags = tags.filter(value => value !== tag);
          if (editing === tag) resetEditor();
          changed();
        }]
      ]) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text;
        button.className = className;
        button.disabled = saving;
        button.setAttribute("aria-label", `${text}: ${tag}`);
        button.addEventListener("click", action);
        actions.append(button);
      }
      row.append(label, actions);
      $("tags").append(row);
    }
  }

  async function request(options) {
    const response = await fetch("/api/tags", options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed.");
    return data;
  }

  $("editor").addEventListener("submit", event => {
    event.preventDefault();
    if (saving || revision === null || editing === null) return;
    const tag = normalize($("tag").value);
    if (!tag) { $("form-error").textContent = "A tag cannot be empty."; return; }
    if (tags.some(value => value === tag && value !== editing)) {
      $("form-error").textContent = "This tag already exists.";
      return;
    }
    tags[tags.indexOf(editing)] = tag;
    resetEditor();
    changed();
    $("search").focus();
  });
  $("cancel").addEventListener("click", resetEditor);
  $("search-form").addEventListener("submit", event => {
    event.preventDefault();
    const tag = normalize($("search").value);
    if (saving || revision === null || !tag || tags.includes(tag)) return;
    tags.push(tag);
    changed();
    $("search").focus();
  });
  $("search").addEventListener("input", render);
  $("save").addEventListener("click", async () => {
    if (!dirty || saving) return;
    saving = true;
    render();
    status("Saving changes…");
    try {
      const data = await request({method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tags, revision})});
      tags = data.tags;
      revision = data.revision;
      dirty = false;
      status("Saved to tags.json. The previous contents are backed up in tags.json.bak.");
    } catch (error) { status(error.message, true); }
    finally { saving = false; render(); }
  });
  window.addEventListener("beforeunload", event => {
    if (dirty) { event.preventDefault(); event.returnValue = ""; }
  });
  request().then(data => {
    tags = data.tags;
    revision = data.revision;
    dirty = data.normalized;
    render();
    status(dirty ? "Tags were normalized and duplicates merged. Click Save to write these changes." : "Tags loaded.");
  }).catch(error => status(error.message, true));
}
