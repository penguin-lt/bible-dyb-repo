-- ============================================================================
-- bible-dyb-repo — canonical schema for the Selah Bible reader
-- Run this in the Supabase SQL editor OR via: supabase db push
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. books : one row per book of the Bible (66 rows)
--    id is the 1-based position in canonical 66-book order
-- ---------------------------------------------------------------------------
create table if not exists public.books (
  id          integer primary key,
  name        text    not null unique,
  testament   text    not null check (testament in ('OT', 'NT')),
  chapters    integer not null
);

comment on table public.books is 'One row per book of the Bible. id = 1..66 in canonical order.';

-- ---------------------------------------------------------------------------
-- 2. verses : one row per verse (primary key is the full reference)
-- ---------------------------------------------------------------------------
create table if not exists public.verses (
  book      integer not null references public.books(id) on delete cascade,
  chapter   integer not null,
  verse     integer not null,
  text      text    not null,
  primary key (book, chapter, verse)
);

create index if not exists verses_text_idx on public.verses using gin (to_tsvector('english', text));
create index if not exists verses_book_chapter_idx on public.verses (book, chapter);

comment on table public.verses is 'Scripture text. Primary key is the reference (book, chapter, verse).';

-- ---------------------------------------------------------------------------
-- 3. Row Level Security — allow anyone to READ (the reader uses the anon key)
--    Writes remain locked down (none for anon/authenticated by default).
-- ---------------------------------------------------------------------------
alter table public.books  enable row level security;
alter table public.verses enable row level security;

drop policy if exists "books are publicly readable"  on public.books;
drop policy if exists "verses are publicly readable" on public.verses;

create policy "books are publicly readable"
  on public.books for select
  to anon, authenticated
  using (true);

create policy "verses are publicly readable"
  on public.verses for select
  to anon, authenticated
  using (true);

-- ---------------------------------------------------------------------------
-- 4. Full-text search helper (English). Used by the app's search when a
--    Postgres FTS endpoint is wired up; the app can also use plain ilike.
-- ---------------------------------------------------------------------------
create or replace function public.search_verses(q text, limit_n integer default 50)
returns table (book integer, chapter integer, verse integer, text text)
language sql stable
as $$
  select v.book, v.chapter, v.verse, v.text
  from public.verses v
  where to_tsvector('english', v.text) @@ plainto_tsquery('english', q)
  order by ts_rank(to_tsvector('english', v.text), plainto_tsquery('english', q)) desc
  limit limit_n;
$$;
