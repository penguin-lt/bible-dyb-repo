import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Creates a Supabase client from environment variables.
 *
 * Required env (see .env.example):
 *   NEXT_PUBLIC_SUPABASE_URL       e.g. https://odjrheaglkptzqiamztn.supabase.co
 *   NEXT_PUBLIC_SUPABASE_ANON_KEY  the publishable "anon" key
 *
 * Returns null if either is missing (the reader will fall back / error clearly).
 */
export function getSupabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false },
  });
}

export function missingEnvMessage(): string {
  return "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in your .env.local (see .env.example).";
}

export const TABLE_BOOKS = () => process.env.SUPABASE_BOOKS_TABLE || "books";
export const TABLE_VERSES = () =>
  process.env.SUPABASE_VERSES_TABLE || "verses";
