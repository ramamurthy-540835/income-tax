import { z } from "zod";
import { isValidPan, normalizePan } from "./identity";
export const profileSchema=z.object({fullName:z.string().trim().min(2).max(120),dateOfBirth:z.iso.date().refine(v=>new Date(`${v}T00:00:00Z`)<new Date(),"Date of birth must be in the past"),pan:z.string().transform(normalizePan).refine(isValidPan,"Invalid PAN format"),email:z.email(),mobile:z.string().regex(/^[6-9][0-9]{9}$/),assessmentYear:z.string().regex(/^AY20[0-9]{2}-[0-9]{2}$/)});
export const consentSchema=z.object({accepted:z.literal(true),consentVersion:z.string().min(1),noticeVersion:z.string().min(1)});
export const createCaseSchema=z.object({profile:profileSchema,processingConsent:consentSchema});
export const preferenceSchema=z.object({caseId:z.uuid(),assessmentYear:z.string(),preference:z.enum(["GROCERY","SERVICES","GOLD"]),confirmationVersion:z.string().min(1),confirmed:z.literal(true)});
