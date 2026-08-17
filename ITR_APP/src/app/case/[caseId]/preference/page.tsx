import { PreferenceForm } from "./preference-form";
import { WorkflowPage } from "@/components/workflow/page-shell";
export default function PreferencePage(){return <WorkflowPage step={5} eyebrow="Step 5 · Preference" title="Select your preference" description="Choose the category you would prefer our team to understand when discussing additional services with you. This preference is separate from your tax deduction calculation."><PreferenceForm/></WorkflowPage>}
