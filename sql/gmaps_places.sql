-- Planned Supabase/Postgres table for the scraped places.
-- Not applied by any script in this repository: review it, then run it once
-- in the Supabase SQL editor when the data has been validated.

create table if not exists public.gmaps_places (
    -- Primary key: Google's place_id, read from the link of every card. The same
    -- place found by several cells or categories always has the same place_id,
    -- so an upsert never duplicates it.
    place_id        text primary key,

    name            text,
    city_code       text        not null,
    queries         text[]      not null default '{}',  -- our searches that found it
    category        text,                               -- Google's label, e.g. 'Art museum'
    rating          numeric(2,1),                       -- e.g. 4.6
    reviews_count   integer,                            -- mostly empty when scraped headless
    lat             double precision not null,
    lng             double precision not null,
    maps_url        text,
    feature_id      text,                               -- Maps internal id (0x...:0x...)
    image_url       text,                               -- thumbnail link, may expire
    rating_label    text,                               -- raw aria-label, re-parsable
    card_text       text,                               -- raw card text, re-parsable

    first_seen_at   timestamptz not null default now(),
    last_scraped_at timestamptz not null default now()
);

create index if not exists gmaps_places_city_idx on public.gmaps_places (city_code);
create index if not exists gmaps_places_queries_idx on public.gmaps_places using gin (queries);
create index if not exists gmaps_places_popularity_idx on public.gmaps_places (city_code, reviews_count desc nulls last);

-- RLS on and no policy: not readable with the public (anon) key.
-- A loader would use the service role key, which bypasses RLS.
alter table public.gmaps_places enable row level security;
