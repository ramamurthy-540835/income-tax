export function CaseSummary({ current = 1 }: { current?: number }) {
  const rows = ["Personal details", "Income documents", "Deductions", "80G analysis", "Preference", "Review"];
  return <aside className="surface side-card" aria-label="Case summary"><div className="eyebrow">Current case</div><h3 style={{marginTop:8}}>AY 2026–27 · Tax review</h3><p className="case-ref">Case TR-2026-000123</p><ul className="summary-list">{rows.map((r,i)=><li key={r}><span>{r}</span><span className={`status ${i+1<current?"ready":i+1===current?"review":""}`}>{i+1<current?"Complete":i+1===current?"In progress":"Not started"}</span></li>)}</ul><p className="fine" style={{marginTop:20}}>Estimates remain subject to evidence validation and professional review.</p></aside>;
}
