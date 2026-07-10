-- Lana AI Prediction Research — RAG knowledge base (schema "lana")
-- Faze 1: bezi bez pgvectoru (embedding = float4[], retrieval = FTS).
-- Po instalaci pgvectoru: ALTER embedding -> vector(1024) + ANN index (migrace pripravena).
CREATE SCHEMA IF NOT EXISTS lana;

-- Zdroje (studie, preprinty, clanky, dokumentace)
CREATE TABLE IF NOT EXISTS lana.sources (
  id          bigserial PRIMARY KEY,
  url         text UNIQUE,
  title       text,
  kind        text,                     -- study | preprint | article | doc | dataset
  authors     text,
  published   date,
  trust       real DEFAULT 0.5,         -- 0..1 duveryhodnost zdroje
  added_at    timestamptz DEFAULT now(),
  meta        jsonb DEFAULT '{}'::jsonb
);

-- Chunky textu + embedding (float4[] fallback; FTS pro retrieval)
CREATE TABLE IF NOT EXISTS lana.chunks (
  id          bigserial PRIMARY KEY,
  source_id   bigint REFERENCES lana.sources(id) ON DELETE CASCADE,
  ord         int,
  content     text NOT NULL,
  embedding   real[],                   -- 1024-dim BGE-M3 (fallback); -> vector(1024) po pgvectoru
  tsv         tsvector,
  created_at  timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON lana.chunks USING gin(tsv);
CREATE INDEX IF NOT EXISTS chunks_src_idx ON lana.chunks(source_id);

-- Findings = extrahovana tvrzeni s epistemickym statusem (jadro self-learning smycky)
CREATE TABLE IF NOT EXISTS lana.findings (
  id              bigserial PRIMARY KEY,
  run_id          bigint,
  claim           text NOT NULL,
  status          text DEFAULT 'pending',   -- corroborated | corroborated_caveat | refuted | pending
  epistemic_level int DEFAULT 0,            -- roste, jak se tvrzeni potvrzuje napric zdroji
  corroborations  int DEFAULT 0,
  refutations     int DEFAULT 0,
  judge_score     real,                     -- 0..1 hodnoceni judge agenta
  evidence        jsonb DEFAULT '[]'::jsonb, -- odkazy na source_id/chunk_id + citace
  created_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS findings_run_idx ON lana.findings(run_id);
CREATE INDEX IF NOT EXISTS findings_status_idx ON lana.findings(status);

-- Bezy research/implementation smycky (zdroj KPI a grafu rustu)
CREATE TABLE IF NOT EXISTS lana.runs (
  id             bigserial PRIMARY KEY,
  kind           text DEFAULT 'research',   -- research | implementation
  started_at     timestamptz DEFAULT now(),
  finished_at    timestamptz,
  sources_added  int DEFAULT 0,
  findings_added int DEFAULT 0,
  db_build_score real,                       -- 0..100 skore budovani DB pro tento beh
  notes          text
);

-- Blueprint pro trading boty (vystup Implementation Loop)
CREATE TABLE IF NOT EXISTS lana.blueprints (
  id          bigserial PRIMARY KEY,
  version     text,
  title       text,
  body        text,                          -- markdown blueprint
  status      text DEFAULT 'draft',          -- draft | approved | live
  created_at  timestamptz DEFAULT now()
);
