const documentsEl = document.querySelector("#documents");
const inputEl = document.querySelector("#paper-input");
const refreshEl = document.querySelector("#refresh-docs");
const docSearchEl = document.querySelector("#doc-search");
const docTypeEl = document.querySelector("#doc-type");
const docSortEl = document.querySelector("#doc-sort");
const docCountEl = document.querySelector("#doc-count");
const graphCountEl = document.querySelector("#graph-count");
const refreshGraphEl = document.querySelector("#refresh-graph");
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

async function loadLabgraphStats() {
  const response = await fetch("/api/labgraph/stats");
  if (!response.ok) {
    graphCountEl.textContent = "Graph unavailable.";
    return;
  }
  const stats = await response.json();
  if (!stats.entities) {
    graphCountEl.textContent = "No graph built yet.";
    return;
  }
  graphCountEl.textContent = `${stats.entities} entities · ${stats.relations} relations`;
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
  await loadLabgraphStats();
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

function relationLabel(relation) {
  return relation ? relation.kind.replaceAll("_", " ") : "related to";
}

function traceNodeById(trace, nodeId) {
  return (trace.path || []).find((node) => node.id === nodeId);
}

function graphEvidenceForSource(source, trace) {
  if (!trace || trace.status !== "found") return [];
  const chunkId = String(source.chunk_id);
  const evidence = [];

  for (const node of trace.path || []) {
    if (node.attrs && node.attrs.source_filename === source.filename) {
      evidence.push({
        key: `node:${node.id}`,
        label: `Node: ${entityKindLabel(node.kind)} · ${node.name}`,
      });
    }
  }

  for (const relation of trace.relations || []) {
    const provenance = relation.provenance || [];
    if (!provenance.includes(chunkId)) continue;
    const sourceNode = traceNodeById(trace, relation.source_id);
    const targetNode = traceNodeById(trace, relation.target_id);
    evidence.push({
      key: `relation:${relation.source_id}:${relation.target_id}:${relation.kind}`,
      label: `Edge: ${sourceNode ? sourceNode.name : relation.source_id} → ${targetNode ? targetNode.name : relation.target_id} · ${relationLabel(relation)}`,
    });
  }

  return evidence.filter(
    (item, index, all) => all.findIndex((other) => other.key === item.key) === index
  );
}

function renderSourceEvidence(source, trace) {
  const evidence = graphEvidenceForSource(source, trace);
  if (!evidence.length) return "";
  return `
    <div class="source-evidence" aria-label="Graph evidence supported by this source">
      ${evidence.map((item) => `<span>${escapeHtml(item.label)}</span>`).join("")}
    </div>
  `;
}

function renderSources(sources, trace) {
  if (!sources || !sources.length) return "";
  return `
    <div class="sources">
      ${sources.map((source, index) => `
        <details class="source">
          <summary>[${index + 1}] ${escapeHtml(source.filename)}, pages ${escapeHtml(source.pages)}</summary>
          ${renderSourceEvidence(source, trace)}
          <p>${escapeHtml(source.text)}</p>
        </details>
      `).join("")}
    </div>
  `;
}

function entityNames(entities) {
  const names = (entities || []).map((entity) => entity.name);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

// Each state explains why there is no path and what to do about it. A trace is
// only ever built from the question that produced the answer beside it, so an
// empty state here is a real finding, not a rendering gap.
function traceNotice(trace) {
  if (trace.status === "no_graph") {
    return {
      title: "No graph built yet",
      detail: "LabGraph extracts people, projects, methods, papers, and decisions from your documents, then connects them with typed relations.",
      action: "Upload papers or notes to build the graph.",
    };
  }
  if (trace.status === "no_entities") {
    return {
      title: "No graph entities in this question",
      detail: "Nothing in this question matched a person, project, method, paper, or decision in the graph.",
      action: "Name two things from your corpus and ask how they connect.",
    };
  }
  if (trace.status === "partial") {
    const matched = entityNames(trace.matched);
    const nearby = entityNames(trace.neighborhood);
    return {
      title: `Only ${matched} matched`,
      detail: nearby
        ? `A path needs two endpoints. ${matched} connects directly to ${nearby}.`
        : `A path needs two endpoints, and ${matched} has no connections in the graph yet.`,
      action: "Add a second entity to the question to trace a path.",
    };
  }
  if (trace.status === "no_path") {
    return {
      title: "No path found",
      detail: `Searched between ${entityNames(trace.matched)} up to ${trace.max_depth} hops. They are not connected in the graph.`,
      action: "Upload the document that links them, or ask about a closer pair.",
    };
  }
  return {
    title: "Graph trace unavailable",
    detail: "The graph could not be searched for this question. The answer and sources are unaffected.",
    action: "Retry the question, or check the graph status in the corpus panel.",
  };
}

function renderTraceNotice(trace) {
  const notice = traceNotice(trace);
  return `
    <div class="graph-trace trace-empty" data-status="${escapeHtml(trace.status)}">
      <div class="trace-header"><strong>Graph trace</strong></div>
      <p class="trace-empty-title">${escapeHtml(notice.title)}</p>
      <p class="trace-empty-detail">${escapeHtml(notice.detail)}</p>
      <p class="trace-empty-action">${escapeHtml(notice.action)}</p>
      ${renderGraphDiagnostics(trace)}
    </div>
  `;
}

function entityKindLabel(kind) {
  if (!kind) return "Entity";
  return kind.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAttrs(attrs) {
  return Object.entries(attrs || {}).map(([key, value]) => `${key}: ${value}`);
}

function renderDetailRows(rows) {
  const visibleRows = rows.filter((row) => row.value);
  if (!visibleRows.length) return "";
  return `
    <dl class="trace-details-grid">
      ${visibleRows.map((row) => `
        <dt>${escapeHtml(row.label)}</dt>
        <dd>${escapeHtml(row.value)}</dd>
      `).join("")}
    </dl>
  `;
}

function renderTraceNodeDetails(node) {
  const aliases = (node.aliases || []).join(", ");
  const attrs = formatAttrs(node.attrs).join("; ");
  const details = renderDetailRows([
    { label: "Canonical id", value: node.id },
    { label: "Aliases", value: aliases },
    { label: "Attributes", value: attrs },
  ]);
  if (!details) return "";
  return `
    <details class="trace-details">
      <summary>Details</summary>
      ${details}
    </details>
  `;
}

function renderTraceRelationDetails(relation) {
  const attrs = formatAttrs(relation && relation.attrs).join("; ");
  const details = renderDetailRows([
    { label: "Relation", value: relation ? relation.kind : "" },
    { label: "Source id", value: relation ? relation.source_id : "" },
    { label: "Target id", value: relation ? relation.target_id : "" },
    { label: "Provenance chunks", value: relation && relation.provenance ? relation.provenance.join(", ") : "" },
    { label: "Attributes", value: attrs },
  ]);
  if (!details) return "";
  return `
    <details class="trace-details trace-edge-details">
      <summary>Edge details</summary>
      ${details}
    </details>
  `;
}

function diagnosticEndpoints(trace) {
  const matched = trace.matched || [];
  if (matched.length >= 2) return matched.map((entity) => entity.name).join(" ↔ ");
  if (matched.length === 1) return `${matched[0].name}; waiting for a second matched entity`;
  return "No graph entities matched";
}

function renderGraphDiagnostics(trace) {
  const path = trace.path || [];
  const matched = trace.matched || [];
  const rows = [
    { label: "Status", value: trace.status },
    { label: "Matched entities", value: matched.length ? matched.map((entity) => entity.name).join(", ") : "None" },
    { label: "Searched endpoints", value: diagnosticEndpoints(trace) },
    { label: "Max depth", value: trace.max_depth ? `${trace.max_depth} hops` : "" },
    { label: "Returned path", value: path.length ? `${path.length} nodes, ${Math.max(0, path.length - 1)} hops` : "No path returned" },
    { label: "Path selection", value: "Prefers paths touching the most named entities, then the shortest path." },
  ];
  return `
    <details class="trace-diagnostics">
      <summary>Graph diagnostics</summary>
      ${renderDetailRows(rows)}
    </details>
  `;
}

function renderTracePath(trace) {
  const nodes = trace.path;
  const steps = nodes.map((node, index) => `
    <li class="trace-step">
      <div class="trace-node">
        <span class="trace-index">${index + 1}</span>
        <span class="trace-kind" data-kind="${escapeHtml(node.kind || "entity")}">${escapeHtml(entityKindLabel(node.kind))}</span>
        <span class="trace-label">${escapeHtml(node.name)}</span>
        ${renderTraceNodeDetails(node)}
      </div>
      ${index < nodes.length - 1 ? `
        <div class="trace-edge">
          <span>${escapeHtml(relationLabel(trace.relations && trace.relations[index]))}</span>
          ${renderTraceRelationDetails(trace.relations && trace.relations[index])}
        </div>
      ` : ""}
    </li>
  `).join("");
  return `
    <div class="graph-trace" data-status="found">
      <div class="trace-header">
        <strong>Graph trace</strong>
        <span>${nodes.length} nodes</span>
      </div>
      <ol class="trace-path" aria-label="Graph traversal path">
        ${steps}
      </ol>
      ${renderGraphDiagnostics(trace)}
    </div>
  `;
}

function renderTrace(trace) {
  if (!trace) return "";
  return trace.status === "found" ? renderTracePath(trace) : renderTraceNotice(trace);
}

async function ask(question) {
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  const pending = addMessage("assistant", "<p>Searching corpus...</p>");
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: 6 }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Query failed.");
  modePill.textContent = payload.mode === "rag" ? "LLM RAG" : "Local retrieval";
  pending.innerHTML = `<p>${escapeHtml(payload.answer)}</p>${renderTrace(payload.trace)}${renderSources(payload.sources, payload.trace)}`;
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
refreshGraphEl.addEventListener("click", loadLabgraphStats);
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
loadLabgraphStats();
