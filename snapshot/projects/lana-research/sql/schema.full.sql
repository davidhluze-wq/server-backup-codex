--
-- PostgreSQL database dump
--

\restrict Aw7Rd3MTuVugN4MA5IL7rjpWfFhtpkmrXfz9Hn95WSgyKmA8mO4YsMPFEzAkwzF

-- Dumped from database version 14.23 (Ubuntu 14.23-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.23 (Ubuntu 14.23-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: lana; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA lana;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: blueprints; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.blueprints (
    id bigint NOT NULL,
    version text,
    title text,
    body text,
    status text DEFAULT 'draft'::text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: blueprints_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.blueprints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: blueprints_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.blueprints_id_seq OWNED BY lana.blueprints.id;


--
-- Name: chunks; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.chunks (
    id bigint NOT NULL,
    source_id bigint,
    ord integer,
    content text NOT NULL,
    embedding real[],
    tsv tsvector,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: chunks_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.chunks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chunks_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.chunks_id_seq OWNED BY lana.chunks.id;


--
-- Name: crew_runs; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.crew_runs (
    id bigint NOT NULL,
    ts timestamp with time zone DEFAULT now(),
    mode text,
    markets_scanned integer,
    signals_made integer,
    trades_made integer,
    notes jsonb
);


--
-- Name: crew_runs_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.crew_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crew_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.crew_runs_id_seq OWNED BY lana.crew_runs.id;


--
-- Name: findings; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.findings (
    id bigint NOT NULL,
    run_id bigint,
    claim text NOT NULL,
    status text DEFAULT 'pending'::text,
    epistemic_level integer DEFAULT 0,
    corroborations integer DEFAULT 0,
    refutations integer DEFAULT 0,
    judge_score real,
    evidence jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    topic text,
    score real
);


--
-- Name: findings_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.findings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: findings_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.findings_id_seq OWNED BY lana.findings.id;


--
-- Name: health; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.health (
    id bigint NOT NULL,
    ts timestamp with time zone DEFAULT now(),
    stats jsonb
);


--
-- Name: health_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.health_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: health_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.health_id_seq OWNED BY lana.health.id;


--
-- Name: plan_queue; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.plan_queue (
    id bigint NOT NULL,
    ord integer,
    title text,
    mode text DEFAULT 'Exploration'::text,
    origin text DEFAULT 'manual'::text,
    theme text,
    domain text,
    status text DEFAULT 'queued'::text,
    why_now text,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: plan_queue_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.plan_queue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: plan_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.plan_queue_id_seq OWNED BY lana.plan_queue.id;


--
-- Name: pnl_snapshots; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.pnl_snapshots (
    id bigint NOT NULL,
    ts timestamp with time zone DEFAULT now(),
    equity real,
    realized real,
    unrealized real,
    open_positions integer,
    win_rate real,
    mode text DEFAULT 'paper'::text
);


--
-- Name: pnl_snapshots_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.pnl_snapshots_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pnl_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.pnl_snapshots_id_seq OWNED BY lana.pnl_snapshots.id;


--
-- Name: runs; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.runs (
    id bigint NOT NULL,
    kind text DEFAULT 'research'::text,
    started_at timestamp with time zone DEFAULT now(),
    finished_at timestamp with time zone,
    sources_added integer DEFAULT 0,
    findings_added integer DEFAULT 0,
    db_build_score real,
    notes text
);


--
-- Name: runs_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: runs_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.runs_id_seq OWNED BY lana.runs.id;


--
-- Name: signals; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.signals (
    id bigint NOT NULL,
    market text,
    question text,
    prob_estimate real,
    market_price real,
    edge real,
    confidence real,
    side text,
    thesis text,
    evidence jsonb,
    status text DEFAULT 'open'::text,
    mode text DEFAULT 'paper'::text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: signals_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.signals_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signals_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.signals_id_seq OWNED BY lana.signals.id;


--
-- Name: sources; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.sources (
    id bigint NOT NULL,
    url text,
    title text,
    kind text,
    authors text,
    published date,
    trust real DEFAULT 0.5,
    added_at timestamp with time zone DEFAULT now(),
    meta jsonb DEFAULT '{}'::jsonb
);


--
-- Name: sources_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.sources_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sources_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.sources_id_seq OWNED BY lana.sources.id;


--
-- Name: trades; Type: TABLE; Schema: lana; Owner: -
--

CREATE TABLE lana.trades (
    id bigint NOT NULL,
    signal_id bigint,
    market text,
    side text,
    size real,
    entry_price real,
    entry_at timestamp with time zone DEFAULT now(),
    exit_price real,
    exit_at timestamp with time zone,
    pnl real,
    status text DEFAULT 'open'::text,
    mode text DEFAULT 'paper'::text
);


--
-- Name: trades_id_seq; Type: SEQUENCE; Schema: lana; Owner: -
--

CREATE SEQUENCE lana.trades_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trades_id_seq; Type: SEQUENCE OWNED BY; Schema: lana; Owner: -
--

ALTER SEQUENCE lana.trades_id_seq OWNED BY lana.trades.id;


--
-- Name: blueprints id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.blueprints ALTER COLUMN id SET DEFAULT nextval('lana.blueprints_id_seq'::regclass);


--
-- Name: chunks id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.chunks ALTER COLUMN id SET DEFAULT nextval('lana.chunks_id_seq'::regclass);


--
-- Name: crew_runs id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.crew_runs ALTER COLUMN id SET DEFAULT nextval('lana.crew_runs_id_seq'::regclass);


--
-- Name: findings id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.findings ALTER COLUMN id SET DEFAULT nextval('lana.findings_id_seq'::regclass);


--
-- Name: health id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.health ALTER COLUMN id SET DEFAULT nextval('lana.health_id_seq'::regclass);


--
-- Name: plan_queue id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.plan_queue ALTER COLUMN id SET DEFAULT nextval('lana.plan_queue_id_seq'::regclass);


--
-- Name: pnl_snapshots id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.pnl_snapshots ALTER COLUMN id SET DEFAULT nextval('lana.pnl_snapshots_id_seq'::regclass);


--
-- Name: runs id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.runs ALTER COLUMN id SET DEFAULT nextval('lana.runs_id_seq'::regclass);


--
-- Name: signals id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.signals ALTER COLUMN id SET DEFAULT nextval('lana.signals_id_seq'::regclass);


--
-- Name: sources id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.sources ALTER COLUMN id SET DEFAULT nextval('lana.sources_id_seq'::regclass);


--
-- Name: trades id; Type: DEFAULT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.trades ALTER COLUMN id SET DEFAULT nextval('lana.trades_id_seq'::regclass);


--
-- Name: blueprints blueprints_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.blueprints
    ADD CONSTRAINT blueprints_pkey PRIMARY KEY (id);


--
-- Name: chunks chunks_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.chunks
    ADD CONSTRAINT chunks_pkey PRIMARY KEY (id);


--
-- Name: crew_runs crew_runs_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.crew_runs
    ADD CONSTRAINT crew_runs_pkey PRIMARY KEY (id);


--
-- Name: findings findings_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.findings
    ADD CONSTRAINT findings_pkey PRIMARY KEY (id);


--
-- Name: health health_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.health
    ADD CONSTRAINT health_pkey PRIMARY KEY (id);


--
-- Name: plan_queue plan_queue_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.plan_queue
    ADD CONSTRAINT plan_queue_pkey PRIMARY KEY (id);


--
-- Name: pnl_snapshots pnl_snapshots_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.pnl_snapshots
    ADD CONSTRAINT pnl_snapshots_pkey PRIMARY KEY (id);


--
-- Name: runs runs_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.runs
    ADD CONSTRAINT runs_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: sources sources_url_key; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.sources
    ADD CONSTRAINT sources_url_key UNIQUE (url);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: chunks_src_idx; Type: INDEX; Schema: lana; Owner: -
--

CREATE INDEX chunks_src_idx ON lana.chunks USING btree (source_id);


--
-- Name: chunks_tsv_idx; Type: INDEX; Schema: lana; Owner: -
--

CREATE INDEX chunks_tsv_idx ON lana.chunks USING gin (tsv);


--
-- Name: findings_run_idx; Type: INDEX; Schema: lana; Owner: -
--

CREATE INDEX findings_run_idx ON lana.findings USING btree (run_id);


--
-- Name: findings_status_idx; Type: INDEX; Schema: lana; Owner: -
--

CREATE INDEX findings_status_idx ON lana.findings USING btree (status);


--
-- Name: chunks chunks_source_id_fkey; Type: FK CONSTRAINT; Schema: lana; Owner: -
--

ALTER TABLE ONLY lana.chunks
    ADD CONSTRAINT chunks_source_id_fkey FOREIGN KEY (source_id) REFERENCES lana.sources(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Aw7Rd3MTuVugN4MA5IL7rjpWfFhtpkmrXfz9Hn95WSgyKmA8mO4YsMPFEzAkwzF

