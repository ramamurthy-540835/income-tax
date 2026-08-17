import { formatIndianRupees, type Paise } from "@/lib/domain/money";
export function Money({ amount }: { amount: Paise }) { const display=formatIndianRupees(amount); return <span aria-label={`${display} Indian rupees`}>{display}</span>; }
