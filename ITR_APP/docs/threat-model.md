# Threat Model

| Threat | Control | Residual/manual requirement |
|---|---|---|
| PAN exposure | No PAN in IDs/URLs/logs; server HMAC fingerprint; masked display; KMS design for persisted raw PAN | Provision pepper and KMS; approve retention need |
| IDOR/cross-client access | Server token verification, ownership lookup, deny-by-default Firestore rules | Emulator and staging penetration tests |
| Signed URL leakage | Short TTL, narrow object key/method, no URL logging, private buckets | Configure signing identity and lifecycle |
| Malicious/spoofed file | Extension/MIME/magic checks, size/page caps, quarantine, malware stage | Select scanning service and operating SLA |
| Active/malformed PDF | Quarantine parser boundary; reject scripts/encryption failures | Worker sandboxing and parser patch process |
| Prompt injection in documents | Document text labelled untrusted; strict schema; no tools/secrets/authorization from model output | Red-team extraction prompts before staging |
| AI exfiltration | Case-scoped payloads, no credentials, regional endpoint decision, minimal excerpts | Processor/model data-residency approval |
| Evidence tampering | SHA-256, object generation, immutable original, provenance metadata, versioning | Retention and legal-hold policy |
| Duplicate event | Document ID + generation + checksum + processing version idempotency | Event replay tests |
| Privilege escalation | Server-controlled custom claims, role gates, staff-only routes and repository checks | Claims administration runbook/MFA |
| Staff compromise | Least privilege, short sessions, audit trails, no raw PAN in queues | Enforce MFA and periodic access review |
| Public bucket | Public access prevention, uniform access, Terraform policy | Organisation policy verification |
| BigQuery over-permission | Server-only writes, protected views, policy-tag/RLS design | Approved groups and policy tags |
| Log leakage | Allowlist structured fields and recursive redaction | Cloud Logging sinks/retention review |
| Forged consent | Authenticated versioned server event, timestamp and minimal IP hash | Approved legal notice/version process |

Uploaded text can never change system instructions, case identity, statutory rules, permissions, payment actions, or review status. AI output can produce only provisional findings and cannot produce `VERIFIED` without deterministic validation and reviewer action.

