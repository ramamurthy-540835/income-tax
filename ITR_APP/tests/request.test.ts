import {describe,expect,it} from "vitest";
import {isAllowedRequestOrigin} from "@/lib/api/origin";

describe("same-origin request protection",()=>{
 it("accepts the public request origin when it differs from the configured canonical URL",()=>{
  expect(isAllowedRequestOrigin("https://preview.taxright.example","https://preview.taxright.example/api/uploads/sign","https://taxright.example")).toBe(true);
 });

 it("rejects a cross-site origin",()=>{
  expect(isAllowedRequestOrigin("https://attacker.example","https://preview.taxright.example/api/uploads/sign","https://taxright.example")).toBe(false);
 });
});
