import type { DataMode } from "./types";

/** Tiny server helper so layout can label the source without heavy imports. */
export function currentMode(): DataMode {
  const m = process.env.DATA_MODE as DataMode | undefined;
  return m === "supabase" ? "supabase" : "demo";
}
