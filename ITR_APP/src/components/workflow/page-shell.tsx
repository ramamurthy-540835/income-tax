import { CaseSummary } from "./case-summary";
import { Stepper } from "./stepper";

export function WorkflowPage({ step, eyebrow, title, description, children }: { step:number; eyebrow:string; title:string; description:string; children:React.ReactNode }) {
  return <main className="page"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="lead">{description}</p><Stepper current={step}/><div className="workflow-layout"><section className="surface panel">{children}</section><CaseSummary current={step}/></div></main>;
}
