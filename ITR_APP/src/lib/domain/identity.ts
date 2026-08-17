import { createHmac } from "node:crypto";
import { uuidv7 } from "uuidv7";

const PAN_PATTERN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

export function normalizePan(value: string): string {
  return value.replace(/\s+/g, "").toUpperCase();
}

export function isValidPan(value: string): boolean {
  return PAN_PATTERN.test(normalizePan(value));
}

export function maskPan(value: string): string {
  const pan = normalizePan(value);
  if (!PAN_PATTERN.test(pan)) return "**********";
  return `${pan.slice(0, 5)}****${pan.slice(-1)}`;
}

export function panFingerprint(value: string, pepper: string): string {
  const pan = normalizePan(value);
  if (!PAN_PATTERN.test(pan)) throw new Error("Invalid PAN");
  if (pepper.length < 32) throw new Error("PAN pepper must contain at least 32 characters");
  return createHmac("sha256", pepper).update(pan, "utf8").digest("hex");
}

export const newClientId = (): string => uuidv7();
export const newCaseId = (): string => uuidv7();
