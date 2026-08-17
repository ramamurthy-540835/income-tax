import "server-only";
import { z } from "zod";

const schema = z.object({
  APP_ENV: z.enum(["local", "dev", "staging", "prod"]).default("local"),
  APP_BASE_URL: z.url().default("http://localhost:3000"),
  GCP_PROJECT_ID: z.string().min(1).optional(),
  GCP_REGION: z.string().default("asia-south1"),
  FIREBASE_PROJECT_ID: z.string().min(1).optional(),
  FIREBASE_CLIENT_EMAIL: z.email().optional(),
  FIREBASE_PRIVATE_KEY: z.string().min(1).optional(),
  FIRESTORE_DATABASE_ID: z.string().default("(default)"),
  BQ_DATASET: z.string().default("taxright_dev"),
  GCS_QUARANTINE_BUCKET: z.string().optional(),
  GCS_DOCUMENT_BUCKET: z.string().optional(),
  GCS_EXPORT_BUCKET: z.string().optional(),
  PAN_HMAC_SECRET_NAME: z.string().optional(),
  SIGNED_URL_TTL_SECONDS: z.coerce.number().int().min(60).max(900).default(600),
  SESSION_COOKIE_NAME: z.string().default("taxright_session")
});

export type ServerEnv = z.infer<typeof schema>;
let cached: ServerEnv | undefined;

export function serverEnv(): ServerEnv {
  if (!cached) cached = schema.parse(process.env);
  return cached;
}

export function requireCloudConfiguration(): ServerEnv & Required<Pick<ServerEnv, "GCP_PROJECT_ID" | "FIREBASE_PROJECT_ID" | "GCS_QUARANTINE_BUCKET" | "GCS_DOCUMENT_BUCKET" | "GCS_EXPORT_BUCKET">> {
  const env = serverEnv();
  const required = ["GCP_PROJECT_ID", "FIREBASE_PROJECT_ID", "GCS_QUARANTINE_BUCKET", "GCS_DOCUMENT_BUCKET", "GCS_EXPORT_BUCKET"] as const;
  for (const key of required) if (!env[key]) throw new Error(`Cloud configuration is incomplete: ${key}`);
  return env as ReturnType<typeof requireCloudConfiguration>;
}
