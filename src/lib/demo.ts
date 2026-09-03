import fs from "node:fs";
import path from "node:path";
import type { BookMeta, Chapter, Verse } from "./types";

/**
 * Reads the bundled public-domain KJV demo dataset (repo root /demo-data).
 * Server-only module: reads from disk at request time so it is never bundled
 * into client JS.
 */

interface IndexEntry {
  n: number;
  name: string;
  chapters: number;
  testament: "OT" | "NT";
}

interface BookFile {
  name: string;
  chapters: string[][];
}

const DATA_DIR = path.join(process.cwd(), "demo-data");
const BOOKS_DIR = path.join(DATA_DIR, "books");

let _index: IndexEntry[] | null = null;

function index(): IndexEntry[] {
  if (!_index) {
    _index = JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "index.json"), "utf-8")
    ) as IndexEntry[];
  }
  return _index;
}

function loadBookFile(id: number): BookFile {
  const file = path.join(BOOKS_DIR, `${String(id).padStart(2, "0")}.json`);
  return JSON.parse(fs.readFileSync(file, "utf-8")) as BookFile;
}

export function listBooks(): BookMeta[] {
  return index().map((e) => ({
    id: e.n,
    name: e.name,
    testament: e.testament,
    chapters: e.chapters,
  }));
}

export function getBook(id: number): BookMeta | null {
  const e = index().find((x) => x.n === id);
  if (!e) return null;
  return { id: e.n, name: e.name, testament: e.testament, chapters: e.chapters };
}

export function getChapter(bookId: number, chapter: number): Chapter | null {
  const book = getBook(bookId);
  if (!book) return null;
  const file = loadBookFile(bookId);
  if (chapter < 1 || chapter > file.chapters.length) return null;
  const textLines = file.chapters[chapter - 1];
  const verses: Verse[] = textLines.map((text, i) => ({
    book: bookId,
    bookName: book.name,
    chapter,
    verse: i + 1,
    text,
  }));
  return { book, chapter, verses };
}

let _all: Verse[] | null = null;

/** Build a flat list of every verse (lazily, cached). Used by demo search. */
function allVerses(): Verse[] {
  if (_all) return _all;
  const out: Verse[] = [];
  for (const book of listBooks()) {
    const file = loadBookFile(book.id);
    file.chapters.forEach((textLines, ci) => {
      textLines.forEach((text, vi) => {
        out.push({
          book: book.id,
          bookName: book.name,
          chapter: ci + 1,
          verse: vi + 1,
          text,
        });
      });
    });
  }
  _all = out;
  return out;
}

export function searchVerses(query: string, limit = 50): Verse[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const haystack = allVerses();
  const matches: Verse[] = [];
  for (const v of haystack) {
    if (v.text.toLowerCase().includes(q)) {
      matches.push(v);
      if (matches.length >= limit) break;
    }
  }
  return matches;
}
