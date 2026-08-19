import {describe,expect,it} from "vitest";
import {firebaseUidHash} from "@/lib/analytics/identity";
describe("analytics identity",()=>{it("maps Firebase identity without exposing the UID",()=>{const uid="synthetic-firebase-user";const hash=firebaseUidHash(uid);expect(hash).toMatch(/^[a-f0-9]{64}$/);expect(hash).not.toContain(uid)})});
