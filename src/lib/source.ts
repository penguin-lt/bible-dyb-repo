import type { BookMeta, Chapter, DataMode, Verse } from "./types";
import * as demo from "./demo";
import * as supq from "./supabaseQueries";

import { currentMode } from "./mode";

export const DATA_MODE: DataMode = currentMode();

export function dataMode(): DataMode {
  return currentMode();
}

export function dataSourceLabel(): string {
  return dataMode() === "supabase" ? "Supabase (live)" : "Bundled demo (KJV)";
}

export async function listBooks(): Promise<BookMeta[]> {
  return DATA_MODE === "supabase" ? supq.listBooks() : demo.listBooks();
}

export async function getBook(id: number): Promise<BookMeta | null> {
  const books = await listBooks();
  return books.find((b) => b.id === id) ?? null;
}

export async function getChapter(
  bookId: number,
  chapter: number
): Promise<Chapter | null> {
  return DATA_MODE === "supabase"
    ? supq.getChapter(bookId, chapter)
    : Promise.resolve(demo.getChapter(bookId, chapter));
}

export async function searchVerses(query: string, limit?: number): Promise<Verse[]> {
  return DATA_MODE === "supabase"
    ? supq.searchVerses(query, limit)
    : Promise.resolve(demo.searchVerses(query, limit));
}
