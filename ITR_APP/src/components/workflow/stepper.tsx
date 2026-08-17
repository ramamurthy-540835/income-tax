import { steps } from "@/lib/workflow";

export function Stepper({ current }: { current: number }) {
  return <ol className="stepper" aria-label={`Step ${current} of ${steps.length}`}>
    {steps.map((step, i) => <li key={step.slug} className={`step ${i + 1 === current ? "active" : i + 1 < current ? "done" : ""}`} aria-current={i + 1 === current ? "step" : undefined}>{i + 1} {step.short}</li>)}
  </ol>;
}
