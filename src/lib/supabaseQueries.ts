import type { BookMeta, Chapter, Verse } from "./types";
import { getSupabase, missingEnvMessage, TABLE_BOOKS, TABLE_VERSES } from "./supabase";

/**
 * Reads Bible content from a Supabase project.
 *
 * Expected (canonical) schema — see db/migration.sql. If your existing
 * tables use different column/table names, run db/introspect.sql in the
 * Supabase SQL editor and adapt the column names below / via the
 * SUPABASE_*_TABLE env vars.
 *
 *   books  (id int pk, name text, testament text, chapters int)
 *   verses (book int, chapter int, verse int, text text,
 *           primary key (book, chapter, verse))
 */

export async function listBooks(): Promise<BookMeta[]> {
  const sb = getSupabase();
  if (!sb) throw new Error(missingEnvMessage());
  const { data, error } = await sb
    .from(TABLE_BOOKS())
    .select("id,name,testament,chapters")
    .order("id");
  if (error) throw new Error(`Supabase listBooks failed: ${error.message}`);
  return (data ?? []).map((r) => ({
    id: Number(r.id),
    name: String(r.name),
    testament: String(r.testament) === "NT" ? "NT" : "OT",
    chapters: Number(r.chapters),
  }));
}

export async function getChapter(bookId: number, chapter: number): Promise<Chapter | null> {
  const sb = getSupabase();
  if (!sb) throw new Error(missingEnvMessage());

  const books = await listBooks();
  const book = books.find((b) => b.id === bookId);
  if (!book) return null;

  const { data, error } = await sb
    .from(TABLE_VERSES())
    .select("chapter,verse,text")
    .eq("book", bookId)
    .eq("chapter", chapter)
    .order("verse");
  if (error) throw new Error(`Supabase getChapter failed: ${error.message}`);
  if (!data || data.length === 0) return null;

  const verses: Verse[] = (data as { verse: number; text: string }[]).map((r) => ({
    book: bookId,
    bookName: book.name,
    chapter,
    verse: Number(r.verse),
    text: String(r.text),
  }));
  return { book, chapter, verses };
}

export async function searchVerses(query: string, limit = 50): Promise<Verse[]> {
  const sb = getSupabase();
  if (!sb) throw new Error(missingEnvMessage());
  const q = query.trim();
  if (!q) return [];

  const { data, error } = await sb
    .from(TABLE_VERSES())
    .select("book,chapter,verse,text")
    .ilike("text", `%${q}%`)
    .limit(limit);
  if (error) throw new Error(`Supabase searchVerses failed: ${error.message}`);

  // Attach book names.
  const books = await listBooks();
  const nameById = new Map(books.map((b) => [b.id, b.name]));

  return (data ?? []).map((r) => ({
    book: Number(r.book),
    bookName: nameById.get(Number(r.book)) ?? String(r.book),
    chapter: Number(r.chapter),
    verse: Number(r.verse),
    text: String(r.text),
  }));
}
