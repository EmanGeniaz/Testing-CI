-- Users are managed by Supabase Auth (auth.users table)
-- We just reference user_id from auth.users

-- Workspaces (one per user by default, can have multiple)
create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  name text not null default 'My Workspace',
  created_at timestamptz default now()
);

-- Sessions (one per agent run)
create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  filename text,
  agent_id text,
  status text default 'idle',
  data jsonb default '{}',  -- the full session blob (raw_data, analyzed_data, schema_config, etc.)
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Runs (tagging runs)
create table public.runs (
  id text primary key,  -- run_id from existing system
  session_id uuid references sessions(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  provider text,
  model text,
  total_rows int,
  completed int default 0,
  status text default 'pending',
  started_at timestamptz default now(),
  completed_at timestamptz,
  data jsonb default '{}'
);

-- MCP connector configs (per user)
create table public.mcp_configs (
  user_id uuid references auth.users(id) on delete cascade,
  connector_id text,
  enabled boolean default false,
  config jsonb default '{}',
  primary key (user_id, connector_id)
);

-- Memory / preferences (per user)
create table public.user_memory (
  user_id uuid primary key references auth.users(id) on delete cascade,
  data jsonb default '{}',  -- learned preferences, outcomes, etc.
  updated_at timestamptz default now()
);

-- Share links (public read-only access to a session)
create table public.share_links (
  token text primary key default encode(gen_random_bytes(16), 'hex'),
  session_id uuid references sessions(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  expires_at timestamptz,
  created_at timestamptz default now()
);

-- Row-level security
alter table workspaces enable row level security;
alter table sessions enable row level security;
alter table runs enable row level security;
alter table mcp_configs enable row level security;
alter table user_memory enable row level security;
alter table share_links enable row level security;

create policy "users can read own workspaces" on workspaces
  for select using (auth.uid() = user_id);
create policy "users can insert own workspaces" on workspaces
  for insert with check (auth.uid() = user_id);

create policy "users can manage own sessions" on sessions
  for all using (auth.uid() = user_id);
create policy "users can manage own runs" on runs
  for all using (auth.uid() = user_id);
create policy "users can manage own mcp configs" on mcp_configs
  for all using (auth.uid() = user_id);
create policy "users can manage own memory" on user_memory
  for all using (auth.uid() = user_id);
create policy "users can manage own share links" on share_links
  for all using (auth.uid() = user_id);

-- Storage bucket for uploaded files (run via SQL editor or dashboard)
-- insert into storage.buckets (id, name, public) values ('uploads', 'uploads', false);
