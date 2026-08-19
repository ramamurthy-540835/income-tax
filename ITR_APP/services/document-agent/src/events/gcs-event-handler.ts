import { parseGcsEvent } from "./event-schema.js";
import type { DocumentPipeline } from "../pipeline/document-pipeline.js";
export const handleGcsEvent=(pipeline:DocumentPipeline,input:unknown)=>pipeline.process(parseGcsEvent(input));
