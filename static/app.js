const documentsEl = document.querySelector("#documents");
const inputEl = document.querySelector("#paper-input");
const refreshEl = document.querySelector("#refresh-docs");
const formEl = document.querySelector("#query-form");
const questionEl = document.querySelector("#question");
const messagesEl = document.querySelector("#messages");
const modePill = document.querySelector("#mode-pill");

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

async function loadDocuments() {
  const response = await fetch("/api/documents");
  const docs = await response.json();
  if (!docs.length) {
    documentsEl.innerHTML = '<div class="meta">No papers uploaded yet.</div>';
    return;
  }
  documentsEl.innerHTML = docs.map((doc) => `
    <article class="doc">
      <strong>${escapeHtml(doc.filename)}</strong>
      <div class="meta">${doc.pages} pages · ${doc.chunks} chunks · ${new Date(doc.created_at).toLocaleString()}</div>
    </article>
  `).join("");
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
