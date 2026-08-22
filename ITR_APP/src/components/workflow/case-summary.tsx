export function CaseSummary({caseId}:{caseId?:string}) {
  return <aside className="surface side-card" aria-label="Case summary"><div className="eyebrow">Current case</div>{caseId?<p className="case-ref">Case {caseId}</p>:<p className="fine">Case details are shown after a case is created.</p>}<p className="fine" style={{marginTop:20}}>Only saved case data and evidence-backed calculations appear in the review.</p></aside>;
}
