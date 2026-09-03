-- ============================================================================
-- bible-dyb-repo — INTROSPECTION SCRIPT
-- ============================================================================
-- Your Bible content already exists in your Supabase project and this app
-- needs to adapt to HOW it is saved. Running the app against real data
-- requires knowing the actual table + column layout.
--
--   Run this file in:  Supabase Dashboard -> SQL Editor  (paste & run)
--
-- It prints everything needed to wire the app: which tables exist, the names
-- that "look like" Bible tables, their columns/types, RLS state, and a few
-- sample rows so you can recognise your data. Paste the output back to me and
-- I will adapt db/migration.sql and src/lib/supabaseQueries.ts to your exact
-- layout (or point the env vars at your existing tables).
-- ============================================================================

-- 1) All tables in the public schema (most likely home for your Bible data)
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;

-- 2) Candidate Bible-ish tables: name hints only, to help spot them
select table_name
from information_schema.tables
where table_schema = 'public'
  and (
        lower(table_name) in ('books','bible','verses','verse','book',
                              'chapters','chapter','selah','selah_bible','kjv','content')
     or lower(table_name) like '%verse%'
     or lower(table_name) like '%book%'
     or lower(table_name) like '%bible%'
     or lower(table_name) like '%chapter%'
     or lower(table_name) like '%scripture%'
     or lower(table_name) like '%passage%'
     or lower(table_name) like '%kjv%'
     or lower(table_name) like '%selah%'
  )
order by table_name;

-- 3) Columns + types for the candidate tables above (tables that actually exist)
select c.table_name, c.column_name, c.data_type, c.is_nullable
from information_schema.columns c
where c.table_schema = 'public'
  and exists (
    select 1
    from information_schema.tables t
    where t.table_schema='public'
      and t.table_name=c.table_name
      and ( lower(t.table_name) in ('books','bible','verses','verse','book','chapters','chapter','selah','selah_bible','kjv','content')
         or lower(t.table_name) like '%verse%'
         or lower(t.table_name) like '%book%'
         or lower(t.table_name) like '%bible%'
         or lower(t.table_name) like '%chapter%'
         or lower(t.table_name) like '%scripture%'
         or lower(t.table_name) like '%passage%'
         or lower(t.table_name) like '%kjv%'
         or lower(t.table_name) like '%selah%' )
  )
order by c.table_name, c.ordinal_position;

-- 4) Row counts for every public table (to see which holds the actual text)
--    Returns table_name + approximate live count.
do $$
declare
  t text;
  c bigint;
begin
  raise notice 'public table row counts:';
  for t in
    select table_name
    from information_schema.tables
    where table_schema='public' and table_type='BASE TABLE'
    order by table_name
  loop
    execute format('select count(*) from public.%I', t) into c;
    raise notice '  %  ->  % rows', t, c;
  end loop;
end $$;

-- 5) RLS status of candidate tables
select tablename, rowsecurity
from pg_tables
where schemaname='public'
order by tablename;

-- 6) Sample rows from candidate tables (first 3 rows each)
do $$
declare
  t text;
begin
  for t in
    select table_name
    from information_schema.tables
    where table_schema='public'
      and ( lower(table_name) in ('books','bible','verses','verse','book','chapters','chapter','selah','selah_bible','kjv','content')
         or lower(table_name) like '%verse%'
         or lower(table_name) like '%book%'
         or lower(table_name) like '%bible%'
         or lower(table_name) like '%chapter%'
         or lower(table_name) like '%scripture%'
         or lower(table_name) like '%passage%'
         or lower(table_name) like '%kjv%'
         or lower(table_name) like '%selah%' )
    order by table_name
  loop
    raise notice E'\n\n===== sample rows: public.% =====', t;
    execute format('select * from public.%I limit 3', t);
  end loop;
end $$;
