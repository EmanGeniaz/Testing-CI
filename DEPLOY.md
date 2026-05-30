# Deploy the Consumer Intelligence Agent

The app is two services that talk to each other over HTTP:

- **Backend** — FastAPI + LangChain. Long-running tagging jobs in background tasks. Hosted on **Render**.
- **Frontend** — Next.js 16 + Tailwind. Hosted on **Vercel**.

Both deploy from this repo (`EmanGeniaz/Testing-CI`, branch `claude/relaxed-bell-I40xJ`).

---

## Prereqs

- A fresh Anthropic API key. **Generate one now**: https://console.anthropic.com/settings/keys (the prior key was exposed in chat logs and should be considered compromised).
- A Render account: https://dashboard.render.com (free signup, paid plan starts at $7/mo for always-on).
- A Vercel account: https://vercel.com (free tier is fine).
- This repo connected to both: GitHub login → install the Render and Vercel GitHub apps and grant them access to `EmanGeniaz/Testing-CI`.

---

## Step 1 — Deploy the backend on Render

The repo includes `render.yaml` at the root which Render reads to auto-configure the service.

1. Render dashboard → **New +** → **Blueprint**.
2. Select the `EmanGeniaz/Testing-CI` repo.
3. Render parses `render.yaml` and shows a service named `ci-agent-backend`. Click **Apply**.
4. Render starts the build. While it builds, click into the service → **Environment** → **Environment Variables**. Set the secret keys (the yaml declares them but with `sync: false`, so they must be filled manually):
   - `ANTHROPIC_API_KEY` = your fresh key from prereqs
   - `OPENAI_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY` — optional, fill if you want to offer those providers in the UI
5. The yaml sets `TEST_ROW_LIMIT=20` by default so SME test runs stop at 20 rows. Change later when ready to run full datasets.
6. Once the build finishes, Render assigns a URL like `https://ci-agent-backend.onrender.com`. **Copy this URL** — you need it for the frontend.
7. Smoke test: open `https://ci-agent-backend.onrender.com/health` in a browser. You should see `{"status":"ok",...}`. Also try `https://ci-agent-backend.onrender.com/report-types` to confirm all three report types are registered.

**Cost:** the `starter` plan ($7/mo) keeps the service always-on. To save money, change `plan: starter` to `plan: free` in `render.yaml` — but then the service sleeps after 15 min idle and Monisha/AD will see a 30s cold start the first time they open the app.

---

## Step 1.5 — Provision Supabase (Postgres + Auth)

The backend supports a Supabase Postgres backend with row-level security in place of the legacy `database.json` file. If you skip this step the app falls back to the JSON-file storage and stays usable for local dev, but you won't get multi-user isolation or share links.

1. Create a project at https://supabase.com → grab the **Project URL** (`https://<project>.supabase.co`) and the **service role key** (Project Settings → API → `service_role` secret).
2. Open the **SQL editor** in the Supabase dashboard and run the contents of `backend/db_schema.sql` once. This creates the `workspaces`, `sessions`, `runs`, `mcp_configs`, `user_memory`, and `share_links` tables and enables row-level security so each user only sees their own data.
3. In the Supabase dashboard → **Storage** → **New bucket**, create a private bucket named `uploads` (or run the commented-out `insert into storage.buckets ...` line at the bottom of `db_schema.sql`).
4. In Render → service → **Environment**, add:
   - `SUPABASE_URL` — your project URL
   - `SUPABASE_SERVICE_KEY` — the service role key from step 1
   - `SUPABASE_JWT_SECRET` — Project Settings → API → **JWT Secret** (used to verify Supabase Auth JWTs offline; without it the backend falls back to calling Supabase to validate every request, which is slower).
5. Redeploy the backend. On startup it auto-detects Supabase via `SUPABASE_URL` and routes all session/run writes to Postgres. Requests now require a Supabase auth `Authorization: Bearer <jwt>` header; the frontend supplies this once a user signs in.

---

## Step 2 — Deploy the frontend on Vercel

1. Vercel dashboard → **Add New** → **Project**.
2. Import `EmanGeniaz/Testing-CI`.
3. **Important:** in the project settings, set **Root Directory** to `frontend`. (Without this Vercel tries to build from the repo root and fails.)
4. Framework preset should auto-detect as **Next.js**.
5. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` = the Render URL from Step 1.6 (e.g. `https://ci-agent-backend.onrender.com`). No trailing slash.
6. Click **Deploy**. Vercel builds and assigns a URL like `https://testing-ci.vercel.app` (or whatever name you pick).

---

## Step 3 — Smoke test end to end

Open the Vercel URL. Then:

1. Upload `Alexion HPP - Data Raw.xlsx` (or any of the raw data files from the OneDrive `Consumer Intelligence Agents` folder).
2. **Schema tab** → pick the text column (Content/Detail/etc.) → **Pharma Social Intelligence** in the new Report Type dropdown → leave provider as Claude → Run.
3. Should tag ~20 rows (the `TEST_ROW_LIMIT` cap) in 1-2 minutes.
4. Workbench tab → see tagged output. Pharma SI produces 1 row per finding, so a 20-row input might produce 5-30 output rows depending on insight density.
5. Export → CSV → spot-check.

Repeat with `Raw Data Gen Z Nike Adidas Lululemon.xlsx` and the Gen Z Brand Tracker report type.

---

## Step 4 — Share with Monisha & AD

Send them the Vercel URL with one-line instructions:

> Upload your data file → Schema tab → pick the text column → pick a Report Type → Run. Test runs cap at 20 rows. Export to CSV when done.

When they're happy with the output and you're ready for real runs: change `TEST_ROW_LIMIT` from `20` to `0` in the Render dashboard (Environment tab) and the cap is removed. The next run can do all 1000 rows.

---

## Troubleshooting

**Backend build fails on Render:** check the deploy log. Most common: a missing dep in `backend/requirements.txt`. Fix locally, commit, push — Render auto-redeploys.

**Frontend builds but shows "Failed to fetch" in browser console:** `NEXT_PUBLIC_API_URL` isn't set or is wrong. Re-check the env var in Vercel → Settings → Environment Variables → make sure it's set for all environments (Production, Preview, Development) → redeploy.

**"CORS blocked" in browser console:** the backend allows `*` so this shouldn't happen. If it does, check that the URL in `NEXT_PUBLIC_API_URL` is exactly the Render URL with no typo.

**Tagging starts but never completes:** look at Render logs (dashboard → service → Logs). Likely an API key issue or rate limit. If using Claude on Anthropic free credits you'll hit limits fast — switch to a paid tier or use Gemini's free tier instead.

**Data disappears after a deploy:** the persistent disk is mounted at `/var/data` per `render.yaml`. If it's not mounting, check Render dashboard → service → Disks. A 1GB disk is included on the starter plan.

---

## Architecture

```
┌─────────────────┐         HTTPS         ┌─────────────────────┐
│  Vercel         │ ────────────────────▶ │  Render             │
│  Next.js 16     │                       │  FastAPI            │
│  frontend/      │                       │  backend/           │
│                 │ ◀──────────────────── │                     │
└─────────────────┘     JSON responses    │  ─ /var/data ◀──────│── 1GB persistent disk
                                          │     database.json    │
                                          │     runs.json        │
                                          │     runs/*.json      │
                                          │     app.log          │
                                          └─────────────────────┘
                                                    │
                                                    ▼
                                          Anthropic / OpenAI / Groq / Gemini APIs
```
