import {WorkflowPage} from "@/components/workflow/page-shell";
import {DeductionWorkspace} from "./deduction-workspace";
export default async function DeductionsPage({params}:{params:Promise<{caseId:string}>}){const {caseId}=await params;return <WorkflowPage step={3} eyebrow="Step 3 · Deductions" title="Find every eligible deduction" description="Upload investment, insurance, education, housing and medical evidence. TaxRight classifies and renames each document and applies deterministic limits."><DeductionWorkspace caseId={caseId}/></WorkflowPage>}
