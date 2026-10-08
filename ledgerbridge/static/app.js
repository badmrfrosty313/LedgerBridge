"use strict";
const $ = (selector) => document.querySelector(selector);
const state = {documents: [], selected: null, detail: null, rules: null, view: "documents", busy: false};
const labels = {documents: "Review queue", imports: "Import documents", exports: "Export history", rules: "Business rules", audit: "Activity log"};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const displayDate = (value) => new Date(value).toLocaleString();
function formatMoney(cents) {
  if (cents === null || cents === undefined) return "—";
  return new Intl.NumberFormat(undefined, {style: "currency", currency: state.rules?.rules.currency || "USD"}).format(cents / 100);
}
function amountInput(cents) { return cents === null || cents === undefined ? "" : (cents / 100).toFixed(2); }
function cents(value) {
  const text = String(value).trim();
  if (!text) return null;
  if (!/^-?\d+(\.\d{1,2})?$/.test(text)) throw new Error("Enter an amount with at most two decimal places.");
  const negative = text.startsWith("-");
  const [whole, fraction = ""] = text.replace(/^-/, "").split(".");
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(result) || result > 1e12) throw new Error("Amount is too large.");
  return negative ? -result : result;
}
function statusInfo(doc) {
  if (doc.status !== "draft") return [doc.status, doc.status[0].toUpperCase() + doc.status.slice(1)];
  return doc.issues.length ? ["exceptions", "Needs attention"] : ["ready", "Ready for review"];
}
function badge(doc) { const [type, text] = statusInfo(doc); return `<span class="badge ${type}">${text}</span>`; }
function notify(message, error = false) {
  const target = $("#notification"); target.textContent = message; target.classList.toggle("error", error); target.hidden = false;
}
async function api(path, method = "GET", data) {
  const options = {method, headers: {}};
  if (data !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify({...data, actor: $("#actor").value.trim()}); }
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}
async function run(task) {
  if (state.busy) return;
  state.busy = true;
  document.querySelectorAll("button").forEach((button) => button.disabled = true);
  try { await task(); } catch (error) { notify(error.message, true); }
  finally { state.busy = false; document.querySelectorAll("button").forEach((button) => button.disabled = false); updateActionStates(); }
}
function updateActionStates() {
  if (!state.detail) return;
  const doc = state.detail;
  const approve = $("#approve-record"); if (approve) approve.disabled = state.busy || doc.issues.length > 0 || doc.status !== "draft";
}
async function refresh() {
  const [documents, rules] = await Promise.all([api("/api/documents"), api("/api/rules")]);
  state.documents = documents.documents; state.rules = rules;
  renderStats(); renderList(); renderRules();
  if (state.selected) await selectDocument(state.selected);
}
function renderStats() {
  const docs = state.documents;
  const needsAttention = docs.filter((d) => d.status === "draft" && d.issues.length).length;
  const ready = docs.filter((d) => d.ready).length;
  const approved = docs.filter((d) => d.status === "approved");
  const cards = [
    ["In the workspace", docs.length, "documents imported", "▤", ""],
    ["Needs attention", needsAttention, "exceptions to resolve", "!", "attention"],
    ["Ready for review", ready, "validated draft records", "✓", "approved"],
    ["Approved to export", approved.length, formatMoney(approved.reduce((sum, d) => sum + (d.fields.total_cents || 0), 0)), "↗", "approved"]
  ];
  $("#stats").innerHTML = cards.map(([label, count, note, icon, className]) => `<div class="stat ${className}"><div class="stat-top">${label}<span class="stat-icon">${icon}</span></div><strong>${count}</strong><small>${escapeHtml(note)}</small></div>`).join("");
  $("#queue-badge").textContent = docs.filter((d) => d.status === "draft").length;
}
function renderList() {
  const query = $("#search").value.toLowerCase(); const filter = $("#filter").value;
  const docs = state.documents.filter((doc) => {
    const fields = doc.fields;
    const status = statusInfo(doc)[0];
    return (filter === "all" || filter === status) && `${fields.vendor || ""} ${fields.document_number || ""} ${doc.source_name}`.toLowerCase().includes(query);
  });
  $("#document-list").innerHTML = docs.length ? docs.map((doc) => `<button class="doc-row ${doc.id === state.selected ? "selected" : ""}" data-id="${doc.id}"><span class="doc-icon">DOC</span><span class="doc-text"><strong>${escapeHtml(doc.fields.vendor || "Vendor needs review")}</strong><small>${escapeHtml(doc.fields.document_number || doc.document_type.replaceAll("_", " "))} · ${escapeHtml(doc.fields.date || "No date")}</small></span><span class="doc-right"><strong>${escapeHtml(formatMoney(doc.fields.total_cents))}</strong>${badge(doc)}</span></button>`).join("") : `<div class="nothing">${state.documents.length ? "No records match this filter." : "Your queue is empty. Load examples to explore."}</div>`;
  $("#document-list").querySelectorAll("[data-id]").forEach((button) => button.addEventListener("click", () => run(() => selectDocument(button.dataset.id))));
}
async function selectDocument(id) {
  state.selected = id; state.detail = await api(`/api/documents/${id}`); renderList(); renderDetail();
}
function textField(key, label, value, disabled, type = "text") {
  return `<label>${label}<input name="${key}" type="${type}" value="${escapeHtml(value || "")}" ${disabled ? "disabled" : ""} maxlength="2000"></label>`;
}
function renderDetail() {
  const doc = state.detail; const fields = doc.fields; const locked = ["exported", "rejected"].includes(doc.status);
  const issueBox = doc.issues.length ? `<div class="issue-box"><strong>${doc.issues.length} item${doc.issues.length === 1 ? "" : "s"} to resolve</strong><ul>${doc.issues.map((issue) => `<li>${escapeHtml(issue.message)}</li>`).join("")}</ul></div>` : `<div class="clear-box">✓ ${doc.status === "exported" ? "Exported snapshot is locked." : "Current fields pass the business rules."}</div>`;
  const amounts = [["subtotal_cents", "Subtotal"], ["tax_cents", "Tax"], ["total_cents", "Total"]].map(([key, label]) => textField(key, label, amountInput(fields[key]), locked)).join("");
  $("#detail").innerHTML = `<div class="detail-head"><div><div class="section-label">DOCUMENT REVIEW</div><h2>${escapeHtml(fields.vendor || "Untitled document")}</h2><small>${escapeHtml(doc.source_name)} · revision ${doc.revision}</small></div>${badge(doc)}</div><div class="detail-body">${issueBox}<form id="edit-form"><div class="section-label">EXTRACTED DETAILS</div>${textField("vendor", "Vendor / payee", fields.vendor, locked)}<div class="form-grid">${textField("document_number", "Document number", fields.document_number, locked)}${textField("date", "Document date", fields.date, locked, "date")}</div><div class="form-grid">${amounts}</div><div class="amount-strip"><span>Document total</span><strong>${escapeHtml(formatMoney(fields.total_cents))}</strong></div><div class="section-label">ACCOUNTING DETAILS</div><div class="form-grid">${textField("account_code", "Account code", fields.account_code, locked)}${textField("department", "Department", fields.department, locked)}</div><label>Review notes<textarea name="notes" rows="2" maxlength="2000" ${locked ? "disabled" : ""}>${escapeHtml(fields.notes || "")}</textarea></label>${locked ? "" : '<button class="secondary" type="submit">Save corrections</button>'}</form><div class="review-actions">${doc.status === "draft" ? '<button class="primary" id="approve-record">Approve record</button><button class="danger" id="reject-record">Reject record</button>' : doc.status === "approved" ? '<button class="secondary" id="reopen-record">Reopen for review</button><button class="danger" id="reject-record">Reject record</button>' : doc.status === "rejected" ? '<button class="secondary" id="reopen-record">Reopen for review</button>' : `<a class="download" href="/api/exports/${doc.export_id}/download">Download its CSV snapshot ↗</a>`}</div><div id="reject-panel" hidden><label>Rejection reason<textarea id="reject-reason" rows="2" maxlength="2000" placeholder="Explain why this record should not be processed"></textarea></label><button class="danger" id="confirm-reject">Confirm rejection</button></div><div class="detail-tabs"><button class="active" data-detail-tab="source">Source text</button><button data-detail-tab="history">Record history</button><button data-detail-tab="warnings">Extraction notes</button></div><div id="source-tab"><pre class="raw">${escapeHtml(doc.raw_text || "No source text")}</pre></div><div id="history-tab" hidden>${eventsHtml(doc.events)}</div><div id="warnings-tab" hidden><p class="muted">These are the original parser observations. Current validation above uses your corrected fields.</p><pre class="raw">${escapeHtml(doc.extraction_warnings.join("\n") || "No parser warnings.")}</pre></div></div>`;
  $("#edit-form").addEventListener("submit", (event) => {event.preventDefault(); run(saveDocument);});
  $("#approve-record")?.addEventListener("click", () => run(() => transition("approve")));
  $("#reject-record")?.addEventListener("click", () => {$("#reject-panel").hidden = !$("#reject-panel").hidden; $("#reject-reason").focus();});
  $("#confirm-reject")?.addEventListener("click", () => run(() => transition("reject", $("#reject-reason").value)));
  $("#reopen-record")?.addEventListener("click", () => run(() => transition("reopen")));
  $("#detail").querySelectorAll("[data-detail-tab]").forEach((button) => button.addEventListener("click", () => {
    $("#detail").querySelectorAll("[data-detail-tab]").forEach((tab) => tab.classList.toggle("active", tab === button));
    for (const name of ["source", "history", "warnings"]) $(`#${name}-tab`).hidden = button.dataset.detailTab !== name;
  }));
  updateActionStates();
}
async function saveDocument() {
  const form = new FormData($("#edit-form")); const fields = {};
  for (const key of ["vendor", "document_number", "date", "account_code", "department", "notes"]) fields[key] = form.get(key) || null;
  for (const key of ["subtotal_cents", "tax_cents", "total_cents"]) fields[key] = cents(form.get(key));
  await api(`/api/documents/${state.selected}`, "PATCH", {fields, revision: state.detail.revision});
  await refresh(); notify("Corrections saved. Any previous approval has been cleared.");
}
async function transition(action, reason = "") {
  if (action === "approve") {
    const form = new FormData($("#edit-form")); const fields = state.detail.fields;
    const changed = ["vendor", "document_number", "date", "account_code", "department", "notes"].some((key) => (form.get(key) || "") !== (fields[key] || "")) || ["subtotal_cents", "tax_cents", "total_cents"].some((key) => cents(form.get(key)) !== fields[key]);
    if (changed) throw new Error("Save your corrections before approving this record.");
  }
  await api(`/api/documents/${state.selected}/${action}`, "POST", {revision: state.detail.revision, reason});
  await refresh(); notify({approve: "Record approved. It is ready for export.", reject: "Record rejected. It will not be exported.", reopen: "Record reopened for review."}[action]);
}
async function loadDemo() {
  const result = await api("/api/demo", "POST", {});
  const added = result.records.filter((record) => !record.existing).length;
  await refresh(); await showView("documents");
  if (!state.selected && result.records.length) await selectDocument(result.records[0].id);
  notify(`${added} demo records added; ${result.records.length - added} already present. Add account codes to resolve their review exceptions.`);
}
function renderRules() {
  const form = $("#rules-form"); const rules = state.rules.rules;
  form.elements.organization.value = rules.organization; form.elements.currency.value = rules.currency;
  form.elements.approval_limit.value = amountInput(rules.approval_limit_cents); form.elements.tolerance.value = rules.reconciliation_tolerance_cents;
  for (const key of ["account_codes", "departments", "required_fields"]) form.elements[key].value = rules[key].join(", ");
}
async function saveRules() {
  const form = $("#rules-form"); const rules = {...state.rules.rules};
  rules.organization = form.elements.organization.value.trim(); rules.currency = form.elements.currency.value.trim();
  rules.approval_limit_cents = cents(form.elements.approval_limit.value); rules.reconciliation_tolerance_cents = Number(form.elements.tolerance.value);
  for (const key of ["account_codes", "departments", "required_fields"]) rules[key] = form.elements[key].value.split(",").map((value) => value.trim()).filter(Boolean);
  await api("/api/rules", "PATCH", {rules, revision: state.rules.revision}); await refresh(); notify("Business rules saved. Previously approved records now require review.");
}
function eventsHtml(events) {
  return events.length ? events.map((event) => `<div class="timeline-item"><strong>${escapeHtml(event.action.replaceAll("_", " "))}</strong> · ${escapeHtml(event.actor)}<small>${escapeHtml(displayDate(event.created_at))}${event.document_id ? " · record " + event.document_id.slice(0, 8) : ""}</small><details><summary>View change details</summary><pre class="raw">${escapeHtml(JSON.stringify(event.detail, null, 2))}</pre></details></div>`).join("") : '<p class="muted">No activity yet.</p>';
}
async function showView(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach((section) => section.hidden = section.id !== view);
  document.querySelectorAll(".nav").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $("#view-name").textContent = labels[view];
  if (view === "exports") {
    const result = await api("/api/exports");
    $("#export-list").innerHTML = result.exports.length ? result.exports.map((item) => `<div class="export-row"><div><strong>Export ${item.id.slice(0, 8)}</strong><small>${escapeHtml(displayDate(item.created_at))} · ${escapeHtml(item.actor)}</small></div><a class="download" href="/api/exports/${item.id}/download">Download CSV ↗</a></div>`).join("") : '<p>No exports yet. Approve records in the review queue, then create a CSV.</p>';
  }
  if (view === "audit") $("#audit-list").innerHTML = eventsHtml((await api("/api/events")).events);
}
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => run(() => showView(button.dataset.view))));
$("#open-import").addEventListener("click", () => run(() => showView("imports")));
$("#refresh").addEventListener("click", () => run(refresh));
$("#load-demo").addEventListener("click", () => run(loadDemo));
$("#demo-import").addEventListener("click", () => run(loadDemo));
$("#search").addEventListener("input", renderList); $("#filter").addEventListener("change", renderList);
$("#text-import").addEventListener("submit", (event) => {
  event.preventDefault(); run(async () => {
    const form = new FormData(event.target); const result = await api("/api/import/text", "POST", {text: form.get("text"), source_name: form.get("source_name")});
    await refresh(); await showView("documents"); await selectDocument(result.records[0].id);
    notify(result.records[0].existing ? "Exact document already exists. Opened its record." : "Document extracted and added to review.");
  });
});
$("#csv-import").addEventListener("submit", (event) => {
  event.preventDefault(); run(async () => {
    const file = event.target.elements.file.files[0]; if (!file) throw new Error("Choose a CSV file.");
    if (file.size > 1000000) throw new Error("CSV limit is 1 MB.");
    const result = await api("/api/import/csv", "POST", {text: await file.text(), source_name: file.name});
    await refresh(); await showView("documents"); if (result.records.length) await selectDocument(result.records[0].id);
    notify(`${result.records.filter((record) => !record.existing).length} records imported. Review them before approving.`);
  });
});
$("#rules-form").addEventListener("submit", (event) => {event.preventDefault(); run(saveRules);});
$("#export-approved").addEventListener("click", () => run(async () => {
  const result = await api("/api/exports", "POST", {}); await refresh(); await showView("exports");
  notify(`${result.record_count} approved records exported. Download the saved CSV below.`);
}));
run(refresh);
