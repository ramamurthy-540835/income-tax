import {WorkflowPage} from "@/components/workflow/page-shell";
import {IncomeWorkspace} from "./income-workspace";
export default async function IncomePage({params}:{params:Promise<{caseId:string}>}){const {caseId}=await params;return <WorkflowPage step={2} eyebrow="Step 2 · Income" title="Upload your income documents" description="Upload Form 16 or salary slips so TaxRight AI can prepare your initial tax computation."><IncomeWorkspace caseId={caseId}/></WorkflowPage>}
