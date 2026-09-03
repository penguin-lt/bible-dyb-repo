# Selah — Bible Reader

A web Bible reader (Next.js 14 + TypeScript) that shows scripture by book,
chapter, and verse, with phrase search. It is built to read from **your
Supabase project** and ships with a fully-working **bundled demo dataset**
(public-domain King James Version, 66 books / 31,102 verses) so it runs with
zero configuration.

```
Browse  →  choose a book  →  read by chapter (prev / next, chapter picker)
Search  →  full-text phrase search with results highlighted
```

---

## 1. Run it right now (demo mode — default)

```bash
npm install
npm run dev
```

Open the printed URL (default `http://localhost:3000`). `DATA_MODE` defaults to
`demo`, which reads the bundled KJV text in `demo-data/`. No database, no keys.

Production build:

```bash
npm run build && npm run start
```

## 2. Point it at your Supabase project (live data)

Your Bible content already lives in your Supabase project. To read from it:

1. **Add your connection details** to a local `.env.local` (copy
   `.env.example`):

   ```
   DATA_MODE=supabase
   NEXT_PUBLIC_SUPABASE_URL=https://odjrheaglkptzqiamztn.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_publishable_anon_key
   ```

   Find the URL + **anon** key under: Supabase Dashboard → **Settings → API**.
   The `sbp_...` *management* access token you shared is **not** the key the
   app uses — the client SDK needs the *anon/public* key above.

2. **Make sure the schema matches** what the reader expects
   (`src/lib/supabaseQueries.ts`):

   - `books  (id, name, testament, chapters)`
   - `verses (book, chapter, verse, text)` — PK `(book, chapter, verse)`

   If your tables already use these names/columns you’re done. If not:

3. **Tell us how your data is actually saved** (one minute):
   open **SQL Editor** in Supabase, paste the contents of **`db/introspect.sql`**,
   and run it. It prints every table/column that looks like Bible content, RLS
   status, row counts, and sample rows. Share the output and the schema/query
   layer gets adapted to match (or use the `SUPABASE_BOOKS_TABLE` /
   `SUPABASE_VERSES_TABLE` env vars to point at differently-*named* tables with
   the same columns).

   ```
   DATA_MODE=supabase
   ...
   SUPABASE_BOOKS_TABLE=my_bible_books
   SUPABASE_VERSES_TABLE=my_bible_verses
   ```

4. `npm run dev` → set `DATA_MODE=supabase`.

### Fresh project? Create + load the schema

If your project is empty, create the tables, then load the bundled KJV text:

```bash
npm run seed:generate   # (re)writes db/seed.sql from demo-data
```

Run in the Supabase **SQL Editor** in this order:
1. `db/migration.sql` — creates `books`, `verses`, indexes, RLS (public read)
2. `db/seed.sql`       — inserts the 66 books + 31,102 KJV verses

> The seed text is the public-domain King James Version — fine as a starting
> dataset. Replace with your own translation later by re-pointing the app at
> your existing tables.

## Security note on the token

The `sbp_...` token is a **personal access token for the Supabase Management
API** (account-level, sensitive). Treat it like a password:
- do **not** commit it — it is not stored anywhere in this repo
- it is **not** needed at runtime by this app (that’s the project’s **anon**
  key) — so don’t paste it into `.env`
- keep it in a password manager; rotate it in the Supabase dashboard if it was
  ever exposed

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_MODE` | `demo` | `demo` = bundled KJV text; `supabase` = live project |
| `NEXT_PUBLIC_SUPABASE_URL` | – | e.g. `https://odjrheaglkptzqiamztn.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | – | publishable anon key |
| `SUPABASE_BOOKS_TABLE` | `books` | override books table name |
| `SUPABASE_VERSES_TABLE` | `verses` | override verses table name |

## Project layout

```
app/
  page.tsx                      # browse books (OT / NT)
  read/[book]/[chapter]/page.tsx# chapter reader (prev/next nav)
  search/page.tsx               # phrase search
  layout.tsx, globals.css
src/
  lib/
    types.ts                    # BookMeta / Verse / Chapter
    source.ts                   # switches demo <-> supabase
    demo.ts                     # reads demo-data from disk (server only)
    supabase.ts                 # Supabase client from env
    supabaseQueries.ts          # listBooks / getChapter / searchVerses
  components/ChapterPicker.tsx  # chapter dropdown (client)
demo-data/                      # bundled KJV demo dataset (66 books)
db/
  migration.sql                 # canonical schema + RLS
  seed.sql                      # generated KJV seed (66 books, 31k verses)
  introspect.sql                # run in SQL editor to reveal your real schema
scripts/
  generate-seed.mjs             # regenerates db/seed.sql
  check-data.mjs                # validates demo-data
```

## Notes & decisions

- **Demo text source:** the KJV is public domain. Files were pulled into
  `demo-data/` from the open
  [`aruljohn/Bible-kjv`](https://github.com/aruljohn/Bible-kjv) dataset, which
  is structured as per-book JSON. Run `npm run check:data` to validate.
- **Demo reading is server-side from disk**, so the ~4 MB dataset is never sent
  to the browser.
- **Search** in demo mode is a simple case-insensitive substring scan (returns
  up to 50). For live Postgres there is a `search_verses(...)` FTS helper in
  `db/migration.sql`; the query layer currently uses `ilike` for parity.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | run dev server |
| `npm run build` / `npm run start` | production build / serve |
| `npm run typecheck` | TypeScript check |
| `npm run check:data` | validate demo dataset |
| `npm run seed:generate` | (re)generate `db/seed.sql` from demo-data |
