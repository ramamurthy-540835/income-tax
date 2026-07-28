"use client";

import { FormEvent, useMemo, useState } from "react";
import { api, apiWithEtag, downloadApiFile, workspacePath } from "../lib/api";

type Customer = { customer_id: string; display_name: string; is_active: boolean };
type Document = { document_id: string; original_filename: string; renamed_filename?: string; detected_document_type?: string; classification_confidence?: number; status: string };
type Analysis = { detected_kind: string; detected_section?: string; din?: string; response_due_date?: string; demand_amount?: string; urgency: string; summary: string; portal_route: string; risk_flags: string[]; recommended_actions: string[]; evidence_to_collect: string[]; questions_to_resolve: string[] };
type Draft = { subject: string; response_text: string; portal_route: string; risk_flags: string[]; missing_information: string[] };
type Calculation = { regime: "old" | "new"; total_income: number; total_tax: number; taxes_paid: number; balance_payable: number; refund: number };
type Automation = { reconciled: Record<string, number | string[]>; old_before_donation: Calculation; maximum_useful_donation_50_percent_limited: number; eligible_80g_deduction: number; old_after_donation: Calculation; tax_reduction_from_donation: number; new_regime?: Calculation; extracted_documents: unknown[]; review_required: boolean };
const AY = "AY_2026-27";

export default function Home() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [latest, setLatest] = useState<Document[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [message, setMessage] = useState("System ready");
  const [busy, setBusy] = useState(false);
  const base = useMemo(() => customerId ? workspacePath(AY, customerId) : "", [customerId]);
  const selectedClient = customers.find(customer => customer.customer_id === customerId);
  const completedSteps = [Boolean(customerId), documents.length > 0, Boolean(analysis || draft), Boolean(automation)].filter(Boolean).length;

  async function run<T>(label: string, task: () => Promise<T>) {
    setBusy(true); setMessage(label);
    try { return await task(); } catch (error) { setMessage(error instanceof Error ? error.message : "Request failed"); throw error; } finally { setBusy(false); }
  }
  async function selectClient(id: string) {
    setCustomerId(id); setLatest([]); setAnalysis(null); setDraft(null); setAutomation(null);
    if (!id) return setDocuments([]);
    setDocuments((await api<{ documents: Document[] }>(`${workspacePath(AY, id)}/documents`)).documents);
  }
  async function loadClients() {
    const result = await run("Loading client workspaces...", () => api<{ customers: Customer[] }>(`/api/assessment-years/${AY}/customers`));
    setCustomers(result.customers); await selectClient(result.customers[0]?.customer_id ?? "");
    setMessage(`${result.customers.length} client workspaces loaded`);
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const taxpayer = { pan: String(form.get("pan")).toUpperCase(), date_of_birth: form.get("dob"), first_name: form.get("first_name"), surname: form.get("surname") };
    if (!customerId) {
      const customer = await run("Creating permanent client workspace in GCP...", () => api<Customer>(`/api/assessment-years/${AY}/clients/onboard`, { method: "POST", body: JSON.stringify({ display_name: form.get("display_name"), preferred_regime: "compare", is_active: form.get("is_active") === "on", profile: { taxpayer, eligibility: {} } }) }));
      setCustomers(items => [customer, ...items]); setCustomerId(customer.customer_id); setMessage(`Created unique ID ${customer.customer_id}`);
    } else {
      const current = await apiWithEtag<Record<string, unknown>>(`${base}/profile`);
      await run("Updating client profile...", () => api(`${base}/profile`, { method: "PUT", headers: current.etag ? { "If-Match": current.etag } : {}, body: JSON.stringify({ ...current.data, taxpayer: { ...(current.data.taxpayer as object), ...taxpayer } }) }));
      await api(`${base}/status`, { method: "PATCH", body: JSON.stringify({ is_active: form.get("is_active") === "on" }) });
      setMessage(`Updated ${customerId}`);
    }
  }
  async function uploadBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const result = await run("Classifying, renaming and securing documents...", () => api<{ documents: Document[]; failed: unknown[] }>(`${base}/documents/batch`, { method: "POST", body: form }));
    setLatest(result.documents); setDocuments((await api<{ documents: Document[] }>(`${base}/documents`)).documents);
    setMessage(`${result.documents.length} classified; ${result.failed.length} need attention`); event.currentTarget.reset();
  }
  async function analyzeNotice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setAnalysis(await run("Analyzing communication...", () => api<Analysis>(`${base}/notices/analyze`, { method: "POST", body: JSON.stringify({ assessment_year: AY, pasted_text: form.get("pasted_text") }) })));
    setMessage("Recommended course ready for review");
  }
  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!analysis) return; const form = new FormData(event.currentTarget); const evidence = String(form.get("evidence") || "");
    const notice = await run("Creating evidence-linked case...", () => api<{ case_id: string }>(`${base}/notices`, { method: "POST", body: JSON.stringify({ kind: analysis.detected_kind, section: analysis.detected_section ?? "To be confirmed", din: analysis.din ?? null, notice_date: form.get("notice_date"), response_due_date: form.get("due_date"), assessment_year: AY, demand_amount: analysis.detected_kind === "outstanding_demand" ? (analysis.demand_amount ?? 0) : null, taxpayer_position: form.get("position"), allegations_or_queries: String(form.get("queries")).split("\n").filter(Boolean), taxpayer_facts: String(form.get("facts")).split("\n").filter(Boolean), requested_relief: form.get("relief"), evidence: evidence ? [{ document_id: evidence, description: "Primary uploaded evidence", page_numbers: [] }] : [] }) }));
    setDraft(await api<Draft>(`${base}/notices/${notice.case_id}/draft`, { method: "POST" })); setMessage("Review draft created");
  }
  async function calculateTax(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const compare = form.get("compare_new") === "on";
    setAutomation(await run("Extracting tax evidence from every uploaded document...", () =>
      api<Automation>(`${base}/automation/calculate?compare_new=${compare}`, { method: "POST" })));
    setMessage("Documents reconciled; tax and maximum donation calculated");
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">A</span><div><strong>AIDIRAC</strong><small>Tax operations</small></div></div>
      <div className="side-client">
        <span>ACTIVE WORKSPACE</span>
        <strong>{selectedClient?.display_name ?? "No client selected"}</strong>
        <small>{customerId ? customerId.slice(-12) : "Choose or create a client"}</small>
        <div className="side-status"><i className={selectedClient?.is_active ? "live" : ""} />{selectedClient?.is_active ? "Active" : "Not active"}</div>
      </div>
      <nav className="side-nav">
        <a href="#overview"><b>⌂</b><span>Overview</span></a>
        <a href="#details"><b>01</b><span>Client details</span></a>
        <a href="#evidence"><b>02</b><span>Evidence vault</span><em>{documents.length}</em></a>
        <a href="#response"><b>03</b><span>Proceedings</span></a>
        <a href="#tax"><b>04</b><span>Tax & reports</span></a>
      </nav>
      <div className="side-progress"><div><span>Workspace progress</span><strong>{completedSteps}/4</strong></div><progress value={completedSteps} max={4} /><small>AY 2026-27 · Evidence controlled</small></div>
      <div className="side-footer"><span>●</span> GCP connected</div>
    </aside>
    <main className="workspace">
    <header className="topbar"><div><span className="eyebrow">CLIENT OPERATIONS / AY 2026-27</span><h1>{selectedClient?.display_name ?? "Tax Desk"}</h1></div><div className={`status ${busy ? "working" : ""}`}><i />{message}</div></header>
    <section className="hero" id="overview"><div><p className="kicker">One client. One evidence trail.</p><h2>From documents to<br /><em>defensible decisions.</em></h2><p>A guided workspace for evidence, proceedings, tax and donation planning.</p></div><div className="hero-stat"><span>WORKSPACE HEALTH</span><strong>{completedSteps === 4 ? "Review ready" : `${completedSteps} of 4 complete`}</strong><div className="hero-meter"><i style={{width: `${completedSteps * 25}%`}} /></div><button onClick={loadClients}>Sync client desk</button></div></section>
    <nav className="steps"><span className="active">01 Details</span><span>02 Uploads</span><span>03 Response</span><span>04 Tax and PDFs</span></nav>
    <section className="command-grid">
      <article><div className="command-icon identity">ID</div><span>Client status</span><strong>{selectedClient?.is_active ? "Active workspace" : "Needs client"}</strong><small>{customerId ? customerId.slice(-10) : "Create a permanent ID"}</small></article>
      <article><div className="command-icon evidence">DOC</div><span>Evidence readiness</span><strong>{documents.length} documents</strong><small>{documents.filter(d => d.status !== "classified").length} need review</small></article>
      <article><div className="command-icon notice">!</div><span>Proceedings</span><strong>{analysis ? analysis.urgency : "No analysis"}</strong><small>{analysis?.detected_section ? `Section ${analysis.detected_section}` : "Paste a communication"}</small></article>
      <article><div className="command-icon tax">₹</div><span>Tax position</span><strong>{automation ? `₹${automation.old_after_donation.balance_payable.toLocaleString("en-IN")}` : "Not calculated"}</strong><small>{automation ? "After donation payable" : "Run evidence extraction"}</small></article>
    </section>

    <div className="workflow">
      <section className="card" id="details">
        <div className="card-title"><b>01</b><div><h3>Client details</h3><p>Saving a new profile creates its permanent unique ID and GCP workspace</p></div></div>
        <label>Existing client<select value={customerId} onChange={e => void selectClient(e.target.value)}><option value="">Create a new client</option>{customers.map(c => <option key={c.customer_id} value={c.customer_id}>{c.is_active ? "●" : "○"} {c.display_name} / {c.customer_id.slice(-6)}</option>)}</select></label>
        {customerId && <div className="client-id"><span>Permanent client ID</span><strong>{customerId}</strong><i>Firestore / GCS / BigQuery</i></div>}
        <form className="form-grid" onSubmit={saveProfile}>
          <label className="span2">Display name<input name="display_name" required={!customerId} /></label><label>PAN<input name="pan" pattern="[A-Za-z]{5}[0-9]{4}[A-Za-z]" required /></label><label>Date of birth<input name="dob" type="date" required /></label><label>First name<input name="first_name" required /></label><label>Surname<input name="surname" required /></label>
          <label className="active-check"><input name="is_active" type="checkbox" defaultChecked /><span className="check-circle">✓</span><span><strong>Active client</strong><small>Available for current work</small></span></label>
          <button className="wide" disabled={busy}>{customerId ? "Update profile" : "Save profile and create client ID"}</button>
        </form><p className="note">AIS passwords are derived in memory from lowercase PAN plus DOB. Client passwords are not stored.</p>
      </section>

      <section className="card vault" id="evidence">
        <div className="card-title"><b>02</b><div><h3>Evidence uploads</h3><p>Upload the complete client pack; classification and naming are automatic</p></div></div>
        <form onSubmit={uploadBatch}><label className="drop batch-drop"><span className="drop-icon">+</span>Client documents<input name="files" type="file" accept=".pdf,.jpg,.jpeg,.png" multiple required /><span>Up to 50 files; 20 MiB each</span></label><button className="wide accent" disabled={!customerId || busy}>Upload, classify and rename</button></form>
        <div className="guard"><strong>GCP evidence controls</strong><span>Original preserved</span><span>Renamed copy</span><span>Client-ID isolation</span><span>SHA-256 hash</span></div>
        {latest.length > 0 && <div className="intake-list">{latest.map(d => <div className="intake-row" key={d.document_id}><i className={d.status === "classified" ? "ok" : "review"} /><div><strong>{d.renamed_filename}</strong><small>{d.detected_document_type} / original retained</small></div><span>{Math.round((d.classification_confidence ?? 0) * 100)}%</span></div>)}</div>}
      </section>

      <section className="card paste-first" id="response">
        <div className="card-title"><b>03</b><div><h3>Notice and demand response</h3><p>Paste the complete communication to receive a recommended course</p></div></div>
        <form className="paste-form" onSubmit={analyzeNotice}><label>Complete communication<textarea name="pasted_text" rows={11} minLength={20} required /></label><button className="wide accent" disabled={!customerId || busy}>Analyze and recommend best course</button></form>
        {analysis && <div className="analysis-panel"><div className="analysis-top"><div><span className="mini">DETECTED PROCEEDING</span><h3>{analysis.summary}</h3><p>{analysis.portal_route}</p></div><span className={`urgency ${analysis.urgency}`}>{analysis.urgency}</span></div>
          <div className="analysis-meta"><div><small>Section</small><strong>{analysis.detected_section ?? "Confirm"}</strong></div><div><small>DIN</small><strong>{analysis.din ?? "Not detected"}</strong></div><div><small>Due date</small><strong>{analysis.response_due_date ?? "Confirm"}</strong></div><div><small>Demand</small><strong>{analysis.demand_amount ? `Rs ${Number(analysis.demand_amount).toLocaleString("en-IN")}` : "Not detected"}</strong></div></div>
          {analysis.risk_flags.length > 0 && <div className="risk-box">{analysis.risk_flags.map(x => <p key={x}>! {x}</p>)}</div>}<div className="advice-grid"><div><h4>Recommended course</h4><ol>{analysis.recommended_actions.map(x => <li key={x}>{x}</li>)}</ol></div><div><h4>Evidence checklist</h4><ul>{analysis.evidence_to_collect.map(x => <li key={x}>{x}</li>)}</ul></div></div>
          <details className="advanced"><summary>Create formal response case</summary><form className="case-form" onSubmit={createCase}><label>Notice date<input name="notice_date" type="date" required /></label><label>Due date<input name="due_date" type="date" required /></label><label>Position<select name="position"><option value="needs_review">Needs review</option><option value="disagree">Disagree</option><option value="partially_agree">Partly agree</option><option value="agree">Agree</option></select></label><label>Evidence<select name="evidence"><option value="">Select</option>{documents.map(d => <option key={d.document_id} value={d.document_id}>{d.renamed_filename ?? d.original_filename}</option>)}</select></label><label className="span2">Queries<textarea name="queries" required /></label><label className="span2">Verified facts<textarea name="facts" /></label><label className="span2">Relief requested<textarea name="relief" required /></label><button className="span2">Create review draft</button></form></details>
        </div>}
        {draft && <div className="draft"><h3>{draft.subject}</h3><pre>{draft.response_text}</pre><button onClick={() => navigator.clipboard.writeText(draft.response_text)}>Copy draft</button></div>}
      </section>

      <section className="card tax-card" id="tax">
        <div className="card-title"><b>04</b><div><h3>Automatic tax and donation calculation</h3><p>Figures are extracted directly from the uploaded Form 16, AIS, 26AS and deduction evidence</p></div></div>
        <form className="tax-form" onSubmit={calculateTax}>
          <div className="automation-source"><strong>{documents.length} client documents available</strong><span>The engine reconciles duplicate Form 16/AIS figures and flags conflicts for review.</span></div>
          <label className="compare-check"><input name="compare_new" type="checkbox" /><span>Also calculate the new-regime comparison</span></label>
          <button className="wide accent" disabled={!customerId || !documents.length || busy}>Extract documents and calculate automatically</button>
        </form>
        {automation && <div className="automation-results">
          <div className="reconciled-strip"><span>{automation.extracted_documents.length} documents extracted</span><span>Salary Rs {Number(automation.reconciled.gross_salary || 0).toLocaleString("en-IN")}</span><span>TDS Rs {Number(automation.reconciled.tds_salary || 0).toLocaleString("en-IN")}</span></div>
          {(automation.reconciled.warnings as string[] ?? []).length > 0 && <div className="risk-box">{(automation.reconciled.warnings as string[]).map(x => <p key={x}>! {x}</p>)}</div>}
          <div className="before-after">
            <article><span>OLD REGIME / BEFORE DONATION</span><h3>Rs {automation.old_before_donation.total_tax.toLocaleString("en-IN")} tax</h3><p>Balance payable: Rs {automation.old_before_donation.balance_payable.toLocaleString("en-IN")}</p></article>
            <article className="donation-focus"><span>MAXIMUM USEFUL DONATION</span><h3>Rs {automation.maximum_useful_donation_50_percent_limited.toLocaleString("en-IN")}</h3><p>Eligible 80G deduction: Rs {automation.eligible_80g_deduction.toLocaleString("en-IN")}</p></article>
            <article><span>OLD REGIME / AFTER DONATION</span><h3>Rs {automation.old_after_donation.total_tax.toLocaleString("en-IN")} tax</h3><p>Final balance payable: Rs {automation.old_after_donation.balance_payable.toLocaleString("en-IN")}</p><small>Tax reduced by Rs {automation.tax_reduction_from_donation.toLocaleString("en-IN")}</small></article>
          </div>
          <button onClick={() => void downloadApiFile(`${base}/calculations/old/pdf`)}>Generate and download old-regime PDF</button>
          {automation.new_regime && <article className="new-comparison"><span>NEW REGIME COMPARISON</span><strong>Rs {automation.new_regime.total_tax.toLocaleString("en-IN")} tax / Rs {automation.new_regime.balance_payable.toLocaleString("en-IN")} payable</strong><button onClick={() => void downloadApiFile(`${base}/calculations/new/pdf`)}>Generate new-regime PDF</button></article>}
        </div>}
      </section>
    </div>
    </main>
  </div>;
}
