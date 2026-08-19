import {describe,expect,it} from "vitest";
import {buildZip} from "../src/export/zip-builder.js";
describe("export",()=>{it("creates a ZIP containing only standard names",()=>{const name="Income/TRAI_ABC123_AY2026-27_FORM16_TEST_20260331_01.pdf";const zip=buildZip([{name,data:Buffer.from("synthetic")}]);expect(zip.subarray(0,4).readUInt32LE()).toBe(0x04034b50);expect(zip.toString("latin1")).toContain(name);expect(zip.toString("latin1")).not.toContain("AAAAA0000A")})});
