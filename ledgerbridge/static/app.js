"use strict";
const $ = (selector) => document.querySelector(selector);
const state = {documents: [], selected: null, detail: null, rules: null, view: "documents", busy: false, session: null, allocationPreviewKey: null, mappingProfile: null, mappingPreview: null};
const labels = {documents: "Review queue", imports: "Import documents", exports: "Export history", rules: "Business rules", audit: "Activity log"};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
function base64File(buffer) { const bytes = new Uint8Array(buffer), chunks = []; for (let index = 0; index < bytes.length; index += 0x8000) chunks.push(String.fromCharCode(...bytes.subarray(index, index + 0x8000))); return btoa(chunks.join("")); }
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
  if (data !== undefined) {
    options.headers["Content-Type"] = "application/json";
    if (state.session?.csrf) options.headers["X-CSRF-Token"] = state.session.csrf;
    options.body = JSON.stringify({...data, actor: state.session?.username || "Demo Reviewer"});
  }
  const response = await fetch(path, options);
  const result = await response.json();
  if (response.status === 401) { location.assign('/login'); throw new Error('Sign in to continue.'); }
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}
async function run(task) {
  if (state.busy) return;
  state.busy = true;
  document.querySelectorAll("button").forEach((button) => button.disabled = true);
  try { await task(); } catch (error) { notify(error.message, true); }
  finally { state.busy = false; document.querySelectorAll("button").forEach((button) => button.disabled = false); updateActionStates(); const save = $("#allocation-save-button"); if (save) save.disabled = !state.allocationPreviewKey; }
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
  const sources=[...new Set(state.documents.map(doc=>doc.source_name).filter(Boolean))].sort();
  const sourceSelect=$("#source-filter"); const oldSource=sourceSelect.value;
  sourceSelect.innerHTML='<option value="">All sources</option>'+sources.map(source=>'<option value="'+escapeHtml(source)+'">'+escapeHtml(source)+'</option>').join("");
  if(sources.includes(oldSource))sourceSelect.value=oldSource;
  const exceptionCodes=[...new Set(state.documents.flatMap(doc=>doc.issues.map(issue=>issue.code)))].sort();
  const exceptionSelect=$("#exception-filter"); const oldException=exceptionSelect.value;
  exceptionSelect.innerHTML='<option value="">All exception types</option>'+exceptionCodes.map(code=>'<option value="'+escapeHtml(code)+'">'+escapeHtml(code.replaceAll("_"," "))+'</option>').join("");
  if(exceptionCodes.includes(oldException))exceptionSelect.value=oldException;
  const sourceFilter=sourceSelect.value; const dateFilter=$("#date-filter").value; const exceptionFilter=exceptionSelect.value;
  const docs = state.documents.filter((doc) => {
    const fields = doc.fields;
    const status = statusInfo(doc)[0];
    const allocationSearch=(doc.allocations||[]).map(item=>item.destination).join(" ");
    return (filter === "all" || filter === status) && (!sourceFilter || doc.source_name===sourceFilter) && (!dateFilter || fields.date===dateFilter) && (!exceptionFilter || doc.issues.some(issue=>issue.code===exceptionFilter)) && `${fields.vendor || ""} ${fields.document_number || ""} ${fields.account_code || ""} ${fields.department || ""} ${fields.date || ""} ${doc.source_name} ${allocationSearch}`.toLowerCase().includes(query);
  });
  $("#document-list").innerHTML = docs.length ? docs.map((doc) => `<button class="doc-row ${doc.id === state.selected ? "selected" : ""}" data-id="${doc.id}"><span class="doc-icon">DOC</span><span class="doc-text"><strong>${escapeHtml(doc.fields.vendor || "Vendor needs review")}</strong><small>${escapeHtml(doc.fields.document_number || doc.document_type.replaceAll("_", " "))} · ${escapeHtml(doc.fields.date || "No date")}</small></span><span class="doc-right"><strong>${escapeHtml(formatMoney(doc.fields.total_cents))}</strong>${badge(doc)}</span></button>`).join("") : `<div class="nothing">${state.documents.length ? "No records match this filter." : "Your queue is empty. Load examples to explore."}</div>`;
  $("#document-list").querySelectorAll("[data-id]").forEach((button) => button.addEventListener("click", () => {
    // Re-selecting the current row must not asynchronously rebuild the detail
    // form and erase edits the reviewer has started entering.
    if (button.dataset.id === state.selected) return;
    run(() => selectDocument(button.dataset.id));
  }));
}
async function selectDocument(id) {
  state.selected = id; state.detail = await api(`/api/documents/${id}`); renderList(); renderDetail();
}
function textField(key, label, value, disabled, type = "text") {
  return `<label>${label}<input name="${key}" type="${type}" value="${escapeHtml(value || "")}" ${disabled ? "disabled" : ""} maxlength="2000"></label>`;
}
function renderDetail() {
  const doc = state.detail; const fields = doc.fields; const locked = ["exported", "rejected"].includes(doc.status) || state.session?.role === 'viewer';
  const issueBox = doc.issues.length ? `<div class="issue-box"><strong>${doc.issues.length} item${doc.issues.length === 1 ? "" : "s"} to resolve</strong><ul>${doc.issues.map((issue) => `<li>${escapeHtml(issue.message)}</li>`).join("")}</ul></div>` : `<div class="clear-box">✓ ${doc.status === "exported" ? "Exported snapshot is locked." : "Current fields pass the business rules."}</div>`;
  const amounts = [["subtotal_cents", "Subtotal"], ["tax_cents", "Tax"], ["total_cents", "Total"]].map(([key, label]) => textField(key, label, amountInput(fields[key]), locked)).join("");
  $("#detail").innerHTML = `<div class="detail-head"><div><div class="section-label">DOCUMENT REVIEW</div><h2>${escapeHtml(fields.vendor || "Untitled document")}</h2><small>${escapeHtml(doc.source_name)} · revision ${doc.revision}</small></div>${badge(doc)}</div><div class="detail-body">${issueBox}<form id="edit-form"><div class="section-label">EXTRACTED DETAILS</div>${textField("vendor", "Vendor / payee", fields.vendor, locked)}<div class="form-grid">${textField("document_number", "Document number", fields.document_number, locked)}${textField("date", "Document date", fields.date, locked, "date")}</div><div class="form-grid">${amounts}</div><div class="amount-strip"><span>Document total</span><strong>${escapeHtml(formatMoney(fields.total_cents))}</strong></div><div class="section-label">ACCOUNTING DETAILS</div><div class="form-grid">${textField("account_code", "Account code", fields.account_code, locked)}${textField("department", "Department", fields.department, locked)}</div><label>Review notes<textarea name="notes" rows="2" maxlength="2000" ${locked ? "disabled" : ""}>${escapeHtml(fields.notes || "")}</textarea></label>${locked ? "" : '<button class="secondary" type="submit">Save corrections</button>'}</form><div class="review-actions">${state.session?.role === 'viewer' ? '' : doc.status === "draft" ? '<button class="primary" id="approve-record">Approve record</button><button class="danger" id="reject-record">Reject record</button>' : doc.status === "approved" ? '<button class="secondary" id="reopen-record">Reopen for review</button><button class="danger" id="reject-record">Reject record</button>' : doc.status === "rejected" ? '<button class="secondary" id="reopen-record">Reopen for review</button>' : `<a class="download" href="/api/exports/${doc.export_id}/download">Download its CSV snapshot ↗</a>`}</div><div id="reject-panel" hidden><label>Rejection reason<textarea id="reject-reason" rows="2" maxlength="2000" placeholder="Explain why this record should not be processed"></textarea></label><button class="danger" id="confirm-reject">Confirm rejection</button></div><div class="detail-tabs"><button class="active" data-detail-tab="source">Source text</button><button data-detail-tab="history">Record history</button><button data-detail-tab="warnings">Extraction notes</button></div><div id="source-tab"><pre class="raw">${escapeHtml(doc.raw_text || "No source text")}</pre></div><div id="history-tab" hidden>${eventsHtml(doc.events)}</div><div id="warnings-tab" hidden><p class="muted">These are the original parser observations. Current validation above uses your corrected fields.</p><pre class="raw">${escapeHtml(doc.extraction_warnings.join("\n") || "No parser warnings.")}</pre></div></div>`;
  $("#edit-form").addEventListener("submit", (event) => {event.preventDefault(); run(saveDocument);});
  const readOnlyAllocation = locked || state.session?.role === "viewer";
  const allocationPanel = `<section class="allocation-panel"><div class="section-label">COST ALLOCATION</div>${doc.allocations.length ? `<ul>${doc.allocations.map(a => `<li>${escapeHtml(a.destination)} · ${escapeHtml(a.percent)}% · ${escapeHtml(formatMoney(a.cents))}</li>`).join("")}</ul>` : '<p class="muted">No allocation is saved. Allocation is optional.</p>'}${readOnlyAllocation ? "" : `<p class="muted">Add destinations and percentages. Review the computed cents, then explicitly confirm saving. A different reviewer must approve changes.</p><div id="allocation-rows" aria-label="Allocation destinations"></div><button class="secondary" id="allocation-add" type="button">Add allocation row</button><div class="form-grid"><label>Reusable template<select id="allocation-template"><option value="">Choose a saved template</option></select></label><button class="secondary" id="allocation-load-template" type="button">Load template into editor</button></div>${state.session?.role === "admin" ? `<div class="form-grid"><label>Template name<input id="allocation-template-name" maxlength="80"></label><button class="secondary" id="allocation-template-save" type="button">Save current rows as template</button></div>` : ""}<div id="allocation-preview" aria-live="polite"></div><button class="secondary" id="allocation-preview-button" type="button">Preview allocation</button><button class="secondary" id="allocation-save-button" type="button" disabled>Confirm allocation save</button>`}</section>`;
  $("#edit-form").insertAdjacentHTML("afterend", allocationPanel);
  state.allocationPreviewKey = null;
  const invalidateAllocationPreview = () => { state.allocationPreviewKey=null; $("#allocation-save-button").disabled=true; $("#allocation-preview").textContent="Inputs changed. Preview again before saving."; };
  const renderAllocationRows = (items) => {
    $("#allocation-rows").innerHTML=items.map((item,index)=>`<div class="form-grid allocation-row" data-index="${index}"><label>Destination ${index+1}<input class="allocation-destination" aria-label="Destination ${index+1}" maxlength="120" value="${escapeHtml(item.destination||"")}"></label><label>Percentage ${index+1}<input class="allocation-percent" aria-label="Percentage ${index+1}" inputmode="decimal" value="${escapeHtml(item.percent||"")}"></label><button class="secondary allocation-remove" type="button" aria-label="Remove destination ${index+1}">Remove</button><span class="allocation-row-error" aria-live="polite"></span></div>`).join("");
    $("#allocation-rows").querySelectorAll("input").forEach(input=>input.addEventListener("input",()=>{invalidateAllocationPreview(); input.closest(".allocation-row").querySelector(".allocation-row-error").textContent="";}));
    $("#allocation-rows").querySelectorAll(".allocation-remove").forEach(button=>button.addEventListener("click",()=>{const current=allocationItemsSafe();current.splice(Number(button.closest(".allocation-row").dataset.index),1);renderAllocationRows(current);invalidateAllocationPreview();}));
  };
  const allocationItems = () => {
    const rows=[...$("#allocation-rows").querySelectorAll(".allocation-row")];
    const items=rows.map(row=>({destination:row.querySelector(".allocation-destination").value.trim(),percent:row.querySelector(".allocation-percent").value.trim()}));
    const destinations=new Set(); let total=0; let invalid=false;
    rows.forEach((row,index)=>{
      const item=items[index],error=row.querySelector(".allocation-row-error");
      let message=!item.destination?"Destination is required.":!/^\d{1,3}(?:\.\d{1,4})?$/.test(item.percent)?"Enter a percentage with up to four decimal places.":"";
      if(!message && destinations.has(item.destination))message="Destination must be unique.";
      if(!message){destinations.add(item.destination);const [whole,fraction=""]=item.percent.split(".");const basis=Number(whole)*10000+Number(fraction.padEnd(4,"0"));if(basis>1000000)message="Percentage cannot exceed 100%.";else total+=basis;}
      error.textContent=message;if(message)invalid=true;
    });
    if(!invalid && total!==1000000 && rows.length){rows.at(-1).querySelector(".allocation-row-error").textContent="Percentages must total exactly 100.0000%.";invalid=true;}
    if(!rows.length)throw new Error("Add at least one allocation destination.");
    if(invalid)throw new Error("Correct the highlighted allocation rows.");
    return items;
  };
  if (!readOnlyAllocation) {
    renderAllocationRows(doc.allocations.map(a=>({destination:a.destination,percent:a.percent})));
    api("/api/allocation-templates").then(result=>{const select=$("#allocation-template");for(const item of result.templates){const option=document.createElement("option");option.value=item.name;option.textContent=`${item.name} (revision ${item.revision})`;select.append(option);}}).catch(error=>notify(error.message,true));
    $("#allocation-add").addEventListener("click",()=>{const items=allocationItemsSafe();items.push({destination:"",percent:""});renderAllocationRows(items);invalidateAllocationPreview();});
    $("#allocation-load-template").addEventListener("click",()=>run(async()=>{const name=$("#allocation-template").value;if(!name)throw new Error("Choose a template first.");const result=await api(`/api/documents/${state.selected}/allocations/template-preview`,"POST",{name});renderAllocationRows(result.items.map(a=>({destination:a.destination,percent:a.percent})));invalidateAllocationPreview();notify("Template loaded into the editor. Preview and confirm it to save.");}));
    $("#allocation-template-save")?.addEventListener("click",()=>run(async()=>{const name=$("#allocation-template-name").value.trim();if(!name)throw new Error("Enter a template name.");const items=allocationItems();const existing=await api("/api/allocation-templates");const match=existing.templates.find(item=>item.name===name);const result=await api("/api/allocation-templates","POST",{name,items,revision:match?.revision});$("#allocation-template").innerHTML='<option value="">Choose a saved template</option>'+result.templates.map(item=>`<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)} (revision ${item.revision})</option>`).join("");notify("Allocation template saved. It has not changed this document.");}));
  }
  function allocationItemsSafe(){return [...$("#allocation-rows").querySelectorAll(".allocation-row")].map(row=>({destination:row.querySelector(".allocation-destination").value.trim(),percent:row.querySelector(".allocation-percent").value.trim()}));}
  const previewAllocations = async () => { const items=allocationItems(); const result=await api(`/api/documents/${state.selected}/allocations/preview`, "POST", {items}); state.allocationPreviewKey=JSON.stringify(items); $("#allocation-preview").innerHTML=`<div class="clear-box"><strong>Preview — inspect before saving</strong><br>${result.items.map(a=>`${escapeHtml(a.destination)}: ${escapeHtml(a.percent)}% = ${escapeHtml(formatMoney(a.cents))}`).join("<br>")}<br>Source ${escapeHtml(formatMoney(result.source_cents))}; allocated ${escapeHtml(formatMoney(result.allocated_cents))}; difference ${escapeHtml(formatMoney(result.difference_cents))}</div>`; $("#allocation-save-button").disabled=false; return result; };
  $("#allocation-preview-button")?.addEventListener("click",()=>run(previewAllocations));
  $("#allocation-save-button")?.addEventListener("click",()=>run(async()=>{ const items=allocationItems(); if(state.allocationPreviewKey!==JSON.stringify(items)) throw new Error("Preview these exact allocation inputs before saving."); await api(`/api/documents/${state.selected}/allocations/confirm`,"POST",{items,revision:state.detail.revision}); await refresh(); notify("Allocations saved. A different reviewer must approve."); }));
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
  form.elements.allow_credits.checked = rules.allow_credits === true;
  for (const key of ["account_codes", "departments", "required_fields"]) form.elements[key].value = rules[key].join(", ");
}
async function saveRules() {
  const form = $("#rules-form"); const rules = {...state.rules.rules};
  rules.organization = form.elements.organization.value.trim(); rules.currency = form.elements.currency.value.trim();
  rules.approval_limit_cents = cents(form.elements.approval_limit.value); rules.reconciliation_tolerance_cents = Number(form.elements.tolerance.value);
  rules.allow_credits = form.elements.allow_credits.checked;
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
    const simulated = state.session?.demo_mode !== false;
    const [result, deliveryResult, reconciliationResult] = await Promise.all([api("/api/exports"), simulated ? api("/api/bridge/deliveries") : Promise.resolve({deliveries: []}), simulated ? api("/api/reconciliation") : Promise.resolve({reconciliations: []})]);
    const deliveries = new Map(deliveryResult.deliveries.map((item) => [item.export_id, item.receipt]));
    const stateLabel = {reconciled:"Reconciled",not_sent:"Not sent to demo ERP",target_unavailable:"Demo target unavailable",export_mismatch:"Export integrity mismatch",receipt_mismatch:"Receipt discrepancy"};
    const reconciliations = reconciliationResult.reconciliations;
    $("#reconciliation-list").innerHTML = reconciliations.length ? reconciliations.map(item => {
      const label=stateLabel[item.delivery_state] || item.delivery_state;
      const deltas=[item.source_mapping_difference_cents,item.mapping_export_difference_cents,item.export_received_difference_cents].filter(value=>value!==null).map(formatMoney).join(" / ");
      return '<div class="reconciliation-row"><div><strong>Export '+escapeHtml(item.export_id.slice(0,8))+' · '+escapeHtml(label)+'</strong><small>Source '+escapeHtml(formatMoney(item.source_total_cents))+' → mapped '+escapeHtml(formatMoney(item.mapped_total_cents))+' → immutable CSV '+escapeHtml(formatMoney(item.export_total_cents))+' → received '+escapeHtml(formatMoney(item.received_total_cents))+'</small><small>'+item.row_count+' posting rows · mapping v'+item.profile_version+' · differences '+escapeHtml(deltas)+'</small></div><span class="badge '+(item.delivery_state==="reconciled"?"approved":"exceptions")+'">'+escapeHtml(label)+'</span></div>';
    }).join("") : '<p class="muted">No mapped exports yet. Legacy CSV snapshots remain one row per source document.</p>';
    $("#export-list").innerHTML = (state.session?.demo_mode === false ? '' : '<p>Optional demo connector: start <code>python -m ledgerbridge.mock_erp</code> in a second terminal, then send an export to its separate ledger. Retrying the same batch does not post twice.</p>') + (result.exports.length ? result.exports.map((item) => `<div class="export-row"><div><strong>Export ${item.id.slice(0, 8)}</strong><small>${escapeHtml(displayDate(item.created_at))} · ${escapeHtml(item.actor)}</small>${deliveries.has(item.id) ? `<small>Demo ERP receipt ${deliveries.get(item.id).receipt_id.slice(0, 8)} · ${deliveries.get(item.id).record_count} records</small>` : ''}</div><div class="export-actions"><a class="download" href="/api/exports/${item.id}/download">Download CSV ↗</a>${state.session?.demo_mode === false || state.session?.role !== 'admin' && state.session?.role !== undefined ? '' : `<button class="secondary" data-send-demo="${item.id}">${deliveries.has(item.id) ? 'Verify / retry demo ERP' : 'Send to demo ERP'}</button>`}</div></div>`).join("") : '<p>No exports yet. Approve records in the review queue, then create a CSV.</p>');
    $("#export-list").querySelectorAll('[data-send-demo]').forEach((button) => button.addEventListener('click', () => run(async () => {
      const receipt = await api(`/api/exports/${button.dataset.sendDemo}/send-demo`, 'POST', {});
      await showView('exports'); notify(`${receipt.record_count} records reconciled with demo ERP. ${receipt.replayed ? 'Existing batch verified; no duplicate posting.' : 'New batch posted.'}`);
    })));
    if (state.session?.role === "viewer") $("#mapping-panel").hidden=true;
    else { $("#mapping-panel").hidden=false; $("#mapping-profile-controls").hidden=state.session?.role!=="admin"; await loadMappingProfile(); }
    $("#reconciliation-list").setAttribute("aria-label", "Export reconciliation results");
    $("#reconciliation-list").setAttribute("role", "region");
    $("#reconciliation-list").hidden = !simulated;
  }
  if (view === "audit") $("#audit-list").innerHTML = eventsHtml((await api("/api/events")).events);
}
async function loadMappingProfile() {
  state.mappingProfile=await api("/api/mapping-profile");
  $("#account-map-editor").value=Object.entries(state.mappingProfile.profile.account_map).map(([source,target])=>`${source} = ${target}`).join("\n");
  $("#expand-allocations").value=String(state.mappingProfile.profile.expand_allocations);
}
async function saveMappingProfile() {
  const account_map={};
  for(const [index,line] of $("#account-map-editor").value.split("\n").entries()) {
    if(!line.trim())continue;
    const parts=line.split("=").map(value=>value.trim());
    if(parts.length!==2 || !parts[0] || !parts[1])throw new Error(`Mapping row ${index+1} must use SOURCE = TARGET.`);
    if(Object.hasOwn(account_map,parts[0]))throw new Error(`Source account ${parts[0]} is mapped more than once.`);
    account_map[parts[0]]=parts[1];
  }
  const profile={...state.mappingProfile.profile,account_map,expand_allocations:$("#expand-allocations").value==="true"};
  await api("/api/mapping/profile","POST",{profile,revision:state.mappingProfile.revision});
  await loadMappingProfile(); state.mappingPreview=null; $("#mapping-preview").textContent="";
  notify("Mapping profile saved. Re-run the dry-run before confirming an export.");
}
async function runMappingDryRun() {
  const preview=await api("/api/mapping/dry-run"); state.mappingPreview=preview;
  const rows=preview.rows.map(row=>`<li>${escapeHtml(row.vendor)} · ${escapeHtml(row.date)} · ${escapeHtml(row.total)} ${escapeHtml(row.currency)} · account ${escapeHtml(row.account_code)}${row.destination?` · ${escapeHtml(row.destination)}`:""} · source ${escapeHtml(row.source_id)}</li>`).join("");
  const rejected=preview.rejected.map(row=>`<li>${escapeHtml(row.source_id)} — ${escapeHtml(row.reason)}</li>`).join("");
  const canConfirm=preview.rows.length && !preview.rejected.length && preview.difference_cents===0 && state.mappingProfile?.actor!==state.session?.username;
  const reviewerNotice=preview.rows.length && state.mappingProfile?.actor===state.session?.username?"A different reviewer must confirm this mapping export.":"";
  $("#mapping-preview").innerHTML=`<div class="${preview.difference_cents===0 && !preview.rejected.length?"clear-box":"issue-box"}"><strong>Dry-run · profile revision ${preview.profile_revision}</strong><p>${preview.rows.length} mapped rows; source ${escapeHtml(formatMoney(preview.source_total_cents))}; mapped ${escapeHtml(formatMoney(preview.mapped_total_cents))}; difference ${escapeHtml(formatMoney(preview.difference_cents))}</p><ul>${rows||"<li>No approved records available.</li>"}</ul>${rejected?`<h3>Rejected or unmapped source records</h3><ul>${rejected}</ul>`:""}${reviewerNotice?`<p>${escapeHtml(reviewerNotice)}</p>`:""}${canConfirm?'<button class="primary" id="confirm-mapped-export" type="button">Confirm mapped export snapshot</button>':""}</div>`;
  $("#confirm-mapped-export")?.addEventListener("click",()=>run(async()=>{const result=await api("/api/mapping/exports","POST",{preview_id:preview.preview_id,revision:preview.profile_revision});state.mappingPreview=null;await refresh();await showView("exports");notify(`${result.record_count} mapped rows exported; ${formatMoney(result.difference_cents)} difference. The immutable snapshot is ready for separate demo ERP delivery.`);}));
}
$("#save-mapping-profile").addEventListener("click",()=>run(saveMappingProfile));
$("#mapping-dry-run").addEventListener("click",()=>run(runMappingDryRun));
document.querySelectorAll(".nav").forEach((button) => button.addEventListener("click", () => run(() => showView(button.dataset.view))));
$("#open-import").addEventListener("click", () => run(() => showView("imports")));
$("#refresh").addEventListener("click", () => run(refresh));
$("#load-demo").addEventListener("click", () => run(loadDemo));
$("#demo-import").addEventListener("click", () => run(loadDemo));
$("#search").addEventListener("input", renderList); $("#filter").addEventListener("change", renderList); $("#source-filter").addEventListener("change", renderList); $("#date-filter").addEventListener("change", renderList); $("#exception-filter").addEventListener("change", renderList);
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
$("#xlsx-import").addEventListener("submit", (event) => {
  event.preventDefault(); run(async () => {
    const target = $("#xlsx-preview"); target.hidden = true; target.textContent = "";
    const file = event.target.elements.file.files[0]; if (!file) throw new Error("Choose an Excel file.");
    if (file.size > 1000000) throw new Error("Excel limit is 1 MB.");
    const content_base64 = base64File(await file.arrayBuffer());
    const result = await api("/api/import/xlsx/preview", "POST", {content_base64, source_name: file.name});
    target.hidden = false;
    target.innerHTML = `<div class="${result.valid ? 'clear-box' : 'issue-box'}"><strong>${result.valid ? `${result.rows.length} rows ready to import` : 'Workbook needs corrections'}</strong><ul>${result.rows.map(row => { const f = row.fields; return `<li>Row ${row.row}: ${escapeHtml(f.vendor || 'Missing vendor')} · ${escapeHtml(f.date || 'Missing date')} · ${escapeHtml(formatMoney(f.total_cents))} · ${escapeHtml(f.account_code || 'No account code')}${row.errors.length ? ` — ${escapeHtml(row.errors.join(' '))}` : ''}</li>`; }).join('')}</ul>${result.valid ? '<button class="primary" id="confirm-xlsx">Confirm import as draft records</button>' : '<p>These are workbook parse errors. Correct them and upload again; business-rule exceptions appear after draft import. Nothing has been imported.</p>'}</div>`;
    $("#confirm-xlsx")?.addEventListener("click", () => run(async () => { const imported = await api("/api/import/xlsx/confirm", "POST", {preview_token: result.preview_token}); await refresh(); await showView("documents"); notify(`${imported.records.filter(r => !r.existing).length} Excel rows imported as drafts. Review them before approving.`); target.hidden = true; }));
  });
});
$("#rules-form").addEventListener("submit", (event) => {event.preventDefault(); run(saveRules);});
$("#export-approved").addEventListener("click", () => run(async () => {
  const result = await api("/api/exports", "POST", {}); await refresh(); await showView("exports");
  notify(`${result.record_count} approved records exported. Download the saved CSV below.`);
}));
async function initialize() {
  const session = await api('/api/session').catch((error) => {
    if (error.message !== 'Route not found.') throw error;
    return {username: 'Demo Reviewer', role: 'admin', csrf: null, demo_mode: true};
  });
  state.session = session;
  $('#identity').textContent = `${session.username} · ${session.role}`;
  $('#workflow-guidance').textContent=session.role==='viewer'?'Viewer access is read-only. Exported snapshots are immutable.':'Imported, edited, or allocated records require a different reviewer for approval. Exported snapshots are immutable.';
  $('#logout').hidden = !session.csrf;
  if (!session.demo_mode) {
    $('#demo-import').hidden = true; $('#load-demo').hidden = true;
  }
  if (session.role === 'viewer') {
    document.querySelector('.nav[data-view="imports"]').hidden = true;
    $('#open-import').hidden = true;
  }
  if (session.role !== 'admin') { $('#export-approved').hidden = true; $('#rules-form button[type="submit"]').hidden = true; }
  await run(refresh);
}
$('#logout').addEventListener('click', () => run(async () => { await api('/api/logout', 'POST', {}); location.assign('/login'); }));
initialize().catch((error) => notify(error.message, true));
