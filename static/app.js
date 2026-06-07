const documentsEl = document.querySelector("#documents");
const inputEl = document.querySelector("#paper-input");
const refreshEl = document.querySelector("#refresh-docs");
const docSearchEl = document.querySelector("#doc-search");
const docTypeEl = document.querySelector("#doc-type");
const docSortEl = document.querySelector("#doc-sort");
const docCountEl = document.querySelector("#doc-count");
const formEl = document.querySelector("#query-form");
const questionEl = document.querySelector("#question");
const messagesEl = document.querySelector("#messages");
const modePill = document.querySelector("#mode-pill");

let allDocuments = [];

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function addMessage(role, html) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.innerHTML = html;
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return node;
}

function documentType(doc) {
  const match = doc.filename.toLowerCase().match(/\.([a-z0-9]+)$/);
  return match ? match[1] : "";
}

function filteredDocuments() {
  const query = docSearchEl.value.trim().toLowerCase();
  const type = docTypeEl.value;
  const sort = docSortEl.value;

  return allDocuments
    .filter((doc) => {
      const matchesQuery = !query || doc.filename.toLowerCase().includes(query);
      const matchesType = type === "all" || documentType(doc) === type;
      return matchesQuery && matchesType;
    })
    .sort((a, b) => {
      if (sort === "name") return a.filename.localeCompare(b.filename);
      if (sort === "pages") return b.pages - a.pages || a.filename.localeCompare(b.filename);
      if (sort === "chunks") return b.chunks - a.chunks || a.filename.localeCompare(b.filename);
      return new Date(b.created_at) - new Date(a.created_at);
    });
}

function renderDocuments() {
  const docs = filteredDocuments();
  docCountEl.textContent = allDocuments.length
    ? `${docs.length} of ${allDocuments.length} documents`
    : "";

  if (!allDocuments.length) {
    documentsEl.innerHTML = '<div class="meta">No papers uploaded yet.</div>';
    return;
  }

  if (!docs.length) {
    documentsEl.innerHTML = '<div class="meta">No documents match these filters.</div>';
    return;
  }

  documentsEl.innerHTML = docs.map((doc) => `
    <article class="doc">
      <div class="doc-title">
        <strong>${escapeHtml(doc.filename)}</strong>
        ${renderDocumentActions(doc)}
      </div>
      <div class="meta">${doc.pages} pages · ${doc.chunks} chunks · ${new Date(doc.created_at).toLocaleString()}</div>
    </article>
  `).join("");
}

function renderDocumentActions(doc) {
  if (!doc.id) return "";
  return `
    <div class="doc-actions">
      <a class="doc-action" href="/api/documents/${doc.id}/file" target="_blank" rel="noopener">Open</a>
      <button class="doc-action" type="button" data-action="rename" data-document-id="${doc.id}">Rename</button>
      <button class="doc-action danger" type="button" data-action="delete" data-document-id="${doc.id}">Delete</button>
    </div>
  `;
}

async function loadDocuments() {
  const response = await fetch("/api/documents");
  allDocuments = await response.json();
  renderDocuments();
}

async function uploadFiles(files) {
  if (!files.length) return;
  const data = new FormData();
  for (const file of files) data.append("files", file);
  addMessage("assistant", "<p>Indexing uploaded papers...</p>");
  const response = await fetch("/api/upload", { method: "POST", body: data });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Upload failed.");
  const summary = payload.results.map((result) => {
    const chunks = result.chunks === null ? "already indexed" : `${result.chunks} chunks`;
    return `${escapeHtml(result.filename)}: ${chunks}`;
  }).join("<br>");
  addMessage("assistant", `<p>${summary}</p>`);
  await loadDocuments();
}

async function updateDocument(documentId, filename) {
  const response = await fetch(`/api/documents/${documentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Rename failed.");
  return payload;
}

async function removeDocument(documentId) {
  const response = await fetch(`/api/documents/${documentId}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Delete failed.");
  return payload;
}

function renderSources(sources) {
  if (!sources || !sources.length) return "";
  return `
    <div class="sources">
      ${sources.map((source, index) => `
        <details class="source">
          <summary>[${index + 1}] ${escapeHtml(source.filename)}, pages ${escapeHtml(source.pages)}</summary>
          <p>${escapeHtml(source.text)}</p>
        </details>
      `).join("")}
    </div>
  `;
}

async function ask(question) {
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  const pending = addMessage("assistant", "<p>Searching papers...</p>");
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: 6 }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Query failed.");
  modePill.textContent = payload.mode === "rag" ? "LLM RAG" : "Local retrieval";
  pending.innerHTML = `<p>${escapeHtml(payload.answer)}</p>${renderSources(payload.sources)}`;
}

inputEl.addEventListener("change", async (event) => {
  try {
    await uploadFiles(event.target.files);
  } catch (error) {
    addMessage("assistant", `<p>${escapeHtml(error.message)}</p>`);
  } finally {
    inputEl.value = "";
  }
});

refreshEl.addEventListener("click", loadDocuments);
docSearchEl.addEventListener("input", renderDocuments);
docTypeEl.addEventListener("change", renderDocuments);
docSortEl.addEventListener("change", renderDocuments);

documentsEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const documentId = button.dataset.documentId;
  const doc = allDocuments.find((item) => String(item.id) === documentId);
  if (!doc) return;

  try {
    if (button.dataset.action === "rename") {
      const filename = window.prompt("Rename document", doc.filename);
      if (filename === null || filename.trim() === doc.filename) return;
      await updateDocument(documentId, filename.trim());
      addMessage("assistant", `<p>Renamed ${escapeHtml(doc.filename)}.</p>`);
      await loadDocuments();
    }

    if (button.dataset.action === "delete") {
      const confirmed = window.confirm(`Delete "${doc.filename}" and its indexed chunks?`);
      if (!confirmed) return;
      await removeDocument(documentId);
      addMessage("assistant", `<p>Deleted ${escapeHtml(doc.filename)}.</p>`);
      await loadDocuments();
    }
  } catch (error) {
    addMessage("assistant", `<p>${escapeHtml(error.message)}</p>`);
  }
});

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question) return;
  questionEl.value = "";
  formEl.querySelector("button").disabled = true;
  try {
    await ask(question);
  } catch (error) {
    addMessage("assistant", `<p>${escapeHtml(error.message)}</p>`);
  } finally {
    formEl.querySelector("button").disabled = false;
  }
});

loadDocuments();
