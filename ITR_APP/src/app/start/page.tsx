import { ProfileForm } from "./profile-form";
import { WorkflowPage } from "@/components/workflow/page-shell";
export const metadata = { title: "Start your tax profile" };
export default function StartPage(){return <WorkflowPage step={1} eyebrow="Step 1 · Personal details" title="Let’s start with your tax profile" description="We’ll use these details to create your secure TaxRight AI case and analyse your eligible tax benefits."><ProfileForm/></WorkflowPage>}
