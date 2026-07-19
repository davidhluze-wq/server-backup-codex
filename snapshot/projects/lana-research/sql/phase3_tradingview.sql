-- Phase 3: TradingView alerts and local paper-account metadata.
-- This schema has no broker credentials and cannot place real orders.

create table if not exists lana.paper_accounts (
  id bigserial primary key,
  name text not null unique,
  currency text not null default 'USD',
  initial_equity real not null check (initial_equity > 0),
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists lana.webhook_events (
  id bigserial primary key,
  provider text not null,
  event_key text not null unique,
  received_at timestamptz not null default now(),
  payload jsonb not null,
  status text not null default 'received',
  signal_id bigint references lana.signals(id),
  error text
);

create index if not exists webhook_events_provider_received_idx
  on lana.webhook_events(provider, received_at desc);
