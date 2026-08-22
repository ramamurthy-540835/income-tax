import { WorkflowPage } from "@/components/workflow/page-shell";
import {ReviewWorkspace} from "./review-workspace";
export default async function ReviewPage({params}:{params:Promise<{caseId:string}>}){const {caseId}=await params;return <WorkflowPage step={6} eyebrow="Step 6 · Review" title="Review your tax case" description="Check the evidence summary before sending the case to a tax professional." caseId={caseId}><ReviewWorkspace caseId={caseId}/></WorkflowPage>}
