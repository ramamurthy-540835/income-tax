"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {currentIdToken} from "@/lib/auth/client";

type Summary={personalDetails:{fullName:string;maskedPan:string};calculation:{grossIncomeRupees:string|null;oldRegimeTaxRupees:string|null;candidateDeductionsRupees:string|null;estimatedTaxAfterDeductionsRupees:string|null};documents:{submitted:number;ready:number;pending:number};donation80G:string|null;preference:string|null};
const money=(value:string|null)=>value===null?"Not available":`₹${new Intl.NumberFormat("en-IN").format(BigInt(value))}`;

export function ReviewWorkspace({caseId}:{caseId:string}){
 const [summary,setSummary]=useState<Summary|null>(null),[error,setError]=useState("");
 useEffect(()=>{let active=true;(async()=>{try{const token=await currentIdToken(),response=await fetch(`/api/cases/${encodeURIComponent(caseId)}`,{headers:{authorization:`Bearer ${token}`},cache:"no-store"}),payload=await response.json();if(!response.ok)throw new Error(payload.error?.message??"Could not load case summary.");if(active)setSummary(payload)}catch(reason){if(active)setError(reason instanceof Error?reason.message:"Could not load case summary.")}})();return()=>{active=false}},[caseId]);
 const items=summary?[["Personal details",`${summary.personalDetails.fullName} · ${summary.personalDetails.maskedPan}`],["Gross income",money(summary.calculation.grossIncomeRupees)],["Old-regime tax estimate",money(summary.calculation.oldRegimeTaxRupees)],["Potential deductions",money(summary.calculation.candidateDeductionsRupees)],["Estimated tax after eligible deductions",money(summary.calculation.estimatedTaxAfterDeductionsRupees)],["Documents",`${summary.documents.submitted} submitted · ${summary.documents.ready} ready · ${summary.documents.pending} processing/review`],["80G",summary.donation80G??"Not available"],["Preference",summary.preference??"Not available"]]:[["Case summary","Loading verified case data…"]];
 return <><div className="summary-list">{items.map(([label,value])=><div className="doc-row" key={label}><div><strong>{label}</strong></div><div style={{textAlign:"right",fontVariantNumeric:"tabular-nums"}}>{value}</div></div>)}</div>{error&&<div className="callout warning" role="alert" style={{marginTop:20}}>{error}</div>}<div className="callout" style={{marginTop:20}}>Figures are estimates and may change after evidence validation and human review.</div><div className="actions"><Link className="button secondary" href={`/case/${caseId}/preference`}>Back</Link><button className="button primary" type="button">Submit for Tax Review</button></div></>;
}
