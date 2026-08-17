export type Paise = bigint;
export const rupeesToPaise = (rupees: number): Paise => BigInt(Math.round(rupees * 100));
export const formatIndianRupees = (amount: Paise): string =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: amount % 100n === 0n ? 0 : 2 }).format(Number(amount) / 100);
