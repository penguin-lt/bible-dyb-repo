/** Canonical data shapes shared across the app and both data sources. */

export type Testament = "OT" | "NT";

export interface BookMeta {
  /** 1-based index in canonical 66-book order. */
  id: number;
  name: string;
  testament: Testament;
  /** number of chapters in the book */
  chapters: number;
}

export interface Verse {
  book: number;
  bookName: string;
  chapter: number;
  verse: number;
  text: string;
}

export type DataMode = "demo" | "supabase";

export interface Chapter {
  book: BookMeta;
  chapter: number;
  verses: Verse[];
}
