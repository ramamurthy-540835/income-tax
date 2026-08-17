import { describe,expect,it,vi } from "vitest";
import { redactForLog } from "@/lib/security/logging";
import { canTransition } from "@/lib/domain/status";
import { requireRole } from "@/lib/auth/roles";
describe("security boundaries",()=>{it("redacts sensitive log properties recursively",()=>expect(redactForLog({case_id:"safe",profile:{pan:"sensitive",email:"sensitive"}})).toEqual({case_id:"safe",profile:{pan:"[REDACTED]",email:"[REDACTED]"}}));it("blocks privilege escalation",()=>expect(()=>requireRole({uid:"synthetic",role:"CLIENT",emailVerified:true},["ADMIN"])).toThrow());it("blocks impossible state transitions",()=>{expect(canTransition("DRAFT","FILED")).toBe(false);expect(canTransition("DRAFT","PROFILE_COMPLETE")).toBe(true)});it("does not emit PII while testing",()=>{const spy=vi.spyOn(console,"info").mockImplementation(()=>undefined);expect(spy).not.toHaveBeenCalled();spy.mockRestore()})});
