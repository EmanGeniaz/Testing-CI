# Consumer Intelligence Agent — Handover Document

**Last updated**: end of build session (Sikander + Claude)
**Project name**: CI Studio (a.k.a. Consumer Intelligence Agent)
**Production URL**: `https://ci.alphametricx.com`
**Test URL**: `https://testing-ci-three.vercel.app`

---

## 1. What this is

An end-to-end **agentic AI platform** for consumer intelligence research. An analyst describes their question, uploads (or pulls) raw data, picks an agent skill, and the platform autonomously:

1. Acquires data (file upload, or via connectors)
2. Cleanses (dedupes, removes noise)
3. Detects schema
4. Tags rows with LLM (per chosen skill)
5. Validates tags
6. Analyzes patterns
7. Generates a narrative report
8. Renders it as an interactive HTML + PPTX

Users can interact through:
- **Auto mode** — pipeline runs end-to-end
- **Inspect mode** — pipeline pauses at each sub-agent for human review (approve / refine)
- **Tabs** — run multiple agents in parallel (browser-style tabs at the top)
- **Compare runs** — side-by-side comparison of multiple agent outputs

---

## 2. Architecture

```
┌────────────────────┐    HTTPS     ┌─────────────────────────┐
│  Vercel            │────────────▶│  Render                  │
│  Next.js 16        │             │  FastAPI                 │
│  ci.alphametricx   │             │  testing-ci.onrender.com │
│                    │◀────────────│                          │
└──────────┬─────────┘   JSON      └─────────────┬────────────┘
           │                                     │
           │ Auth                                │ Data
           ▼                                     ▼
   ┌──────────────┐                  ┌──────────────────────┐
   │  Supabase    │                  │ /opt/render/project  │
   │  Auth + DB   │                  │   /data/snapshot.json│
   │  +ZeptoMail  │                  │   (persistent disk)  │
   └──────────────┘                  └──────────────────────┘
                                               │
                                               ▼
                              Anthropic Opus (orchestrator)
                              OpenAI GPT-4o-mini (tagging)
                              Optionally: Gemini, Groq
```

### Key components

| Layer | Tech | Hosted on |
|-------|------|-----------|
| Frontend | Next.js 16 (Turbopack) + Tailwind 4 + Newsreader/Inter/JetBrains Mono | Vercel |
| Backend API | FastAPI (Python 3.11) + LangChain + Anthropic SDK | Render (starter $7/mo) |
| Orchestrator | Claude Opus with `tool_use` (ReAct loop) | Inline in backend |
| Tagging engine | OpenAI GPT-4o-mini via langchain-openai | Inline in backend |
| Database | Supabase Postgres (when SUPABASE_URL set) OR JSON file fallback | Supabase / Render disk |
| Auth | Supabase Auth (magic link via ZeptoMail SMTP) — **currently disabled** | Supabase |
| Email | ZeptoMail (smtp.zeptomail.in:587) for magic links | ZeptoMail (paid sub) |
| Storage | Supabase Storage bucket `uploads` (when enabled) | Supabase |
| Persistence | snapshot.json on Render persistent disk | `/opt/render/project/data/` |

---

## 3. Repositories

### Production (current target)
- **GitHub org**: `InfoVision-Agentic-AI`
- **Repo**: `ci-studio`
- **URL**: https://github.com/InfoVision-Agentic-AI/ci-studio
- **Default branch**: `main`
- **Vercel project tracks**: `main`

### Development / test (where we built everything)
- **GitHub**: https://github.com/EmanGeniaz/Testing-CI
- **Branch**: `claude/relaxed-bell-I40xJ`
- **Vercel project**: `testing-ci-three.vercel.app`
- **Render service**: `ci-agent-backend` (URL: `https://testing-ci.onrender.com`)

> **Currently the prod and dev backends are the same Render service.** Eventually you'll want a separate prod backend on Render too.

### How to deploy updates

**Dev (Sikander's workflow):** push to `claude/relaxed-bell-I40xJ` on `EmanGeniaz/Testing-CI` → Vercel `testing-ci-three` auto-deploys.

**Prod:** changes need to land on `InfoVision-Agentic-AI/ci-studio:main`. Two options:
1. **GitHub web UI edit**: edit file directly in the prod repo (quick for tiny fixes)
2. **Local sync**: download zip from dev branch, `git push --force` to prod main (full sync)

> **TODO for next dev**: set up a CI/CD action to mirror dev branch → prod main automatically.

---

## 4. Third-party services & accounts

| Service | Account / Project | Purpose | Credentials location |
|---------|-------------------|---------|---------------------|
| **Vercel** | Sikander's prod team | Frontend hosting | Vercel dashboard |
| **Render** | Sikander's account | Backend hosting | Render dashboard, $7/mo starter plan |
| **Supabase** | `yjspkbtyvjbfvebygvcq` project | Auth + Postgres + Storage | https://supabase.com/dashboard/project/yjspkbtyvjbfvebygvcq |
| **ZeptoMail** | alphametricx.com domain | Transactional email (magic links) | ZeptoMail dashboard, India region |
| **OpenAI** | API key in Render env | GPT-4o-mini for tagging | https://platform.openai.com |
| **Anthropic** | API key in Render env | Opus for orchestrator + report generation | https://console.anthropic.com |
| **Gemini (Google)** | Optional fallback | Free tier alternative | https://aistudio.google.com |
| **Groq** | Optional fallback | Free fast inference | https://console.groq.com |

### Domain & DNS
- **Domain**: `alphametricx.com`
- **Subdomain**: `ci.alphametricx.com` → CNAME → `b34b64e83b3ca6d7.vercel-dns-016.com.`
- **ZeptoMail domain verification**: DNS records (SPF, DKIM, return-path) added on alphametricx.com

---

## 5. Environment variables

### Render (backend) — required
```bash
ANTHROPIC_API_KEY=<sk-ant-...>
OPENAI_API_KEY=<sk-...>             # used for tagging
ANTHROPIC_MODEL=claude-opus-4-5     # orchestrator + report generation
TAGGING_PROVIDER=openai             # which provider does tagging
TAGGING_MODEL=gpt-4o-mini           # which model does tagging
TEST_ROW_LIMIT=0                    # 0 = no cap; set 20-50 for testing
MAX_WORKERS=30                      # tagging concurrency (don't exceed 40)
BATCH_SIZE=15                       # rows per tagging batch
PYTHON_VERSION=3.11.9
DATA_DIR=/opt/render/project/data   # persistent disk path
```

### Render (backend) — Supabase (currently REMOVED to disable auth)
```bash
# Add these back to re-enable auth:
SUPABASE_URL=https://yjspkbtyvjbfvebygvcq.supabase.co
SUPABASE_SERVICE_KEY=<service role key>
SUPABASE_JWT_SECRET=<JWT secret from Supabase API settings>
```

### Vercel (frontend) — Production
```bash
NEXT_PUBLIC_API_URL=https://testing-ci.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://yjspkbtyvjbfvebygvcq.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon public key>
```

> **Note**: the frontend env vars must be set for the **Production** environment specifically (Vercel has Production / Preview / Development).

---

## 6. Core concepts

### Agents
The 7 user-facing agent types (in `frontend/app/components/StudioView.tsx`):
- **Brand Insights** — `explainable_ai_tagging` skill
- **Category Insights** — falls back to default skill
- **Competitive Intelligence** — falls back to default skill
- **Issues & Crisis** — falls back to default skill
- **Pharma Social Intelligence** — `pharma_social_intelligence` skill
- **Gen Z Brand Tracker** — `genz_brand_tracker` skill
- **Create Your Own** — custom prompt; orchestrator picks the skill

### Sub-agents (the pipeline)
Each agent run goes through 9 sub-agents:
1. **Data Acquisition** — file upload or connector pull
2. **Data Sanitization** — dedupe, remove noise (`_cleanse_data` in main.py)
3. **Schema Detection** — pick text column, choose skill
4. **Auto-Tagging** — row-by-row LLM tagging
5. **Tag Validation** — confidence + sanity checks
6. **Pattern Analysis** — theme/sentiment distributions
7. **Insight Generation** — LLM-generated narrative findings
8. **Design & Styling** — template selection
9. **Report Rendering** — HTML/PPTX/CSV/XLSX output

### Skills
Three built-in tagging schemas defined in `backend/report_types/`:
- `explainable_ai_tagging` — generic brand/sentiment/theme/signal extraction with XAI rationale
- `pharma_social_intelligence` — multi-finding: stage, theme, unmet need, concern, QoL impact
- `genz_brand_tracker` — 8 Gen Z value scores + brand metrics

Skill registry at `backend/skill_registry.py` supports uploading custom skills as JSON.

### Methodology
Two methodology docs encoded in `backend/methodology.py`:
- **AD's 13-step analytical methodology** — business objective → storytelling
- **Monisha's 19-step operational workflow** — the ask → human validation

Both are injected into the orchestrator's system prompt so the agent follows the process.

### Memory
`backend/skill_memory.py` tracks past runs and learns:
- Preferred report types per data domain
- Provider/model preferences
- Common refinement feedback patterns ("sharper findings", "more patient voice", etc.)

Memory context is injected into the orchestrator's system prompt. Frontend displays it in the "Memory" sidebar panel.

### Connectors (MCP)
`backend/mcp_registry.py` defines 11 connectors. Two have **real working** integrations:
- **Reddit** — via `praw` library (needs client_id + client_secret)
- **News API** — via newsapi.org (free tier, 100 reqs/day)

Others (Brandwatch, Meltwater, Sprinklr, Talkwalker, Twitter, Meta, InfoVision API, Google Trends, Canva, Claude Design) are UI placeholders showing "Coming soon" — need API integration work.

When enabled in the sidebar's Connectors panel, the connector card unlocks in the agent workspace and can pull data directly into a session.

### Orchestrator
`backend/orchestrator.py` implements a ReAct loop using **Claude Opus with tool_use**:
- 8 tools: `analyze_data_quality`, `select_skill`, `create_custom_schema`, `clean_data`, `run_tagging`, `analyze_patterns`, `generate_report`, `self_review`
- Streams events as NDJSON: `thinking`, `tool_call`, `tool_result`, `checkpoint`, `complete`, `error`
- Frontend (`AgentInspectorModal.tsx`) parses events and updates the pipeline visualization in real time
- In **Inspect mode**, orchestrator emits `checkpoint` events after each tool and waits for the user to call `/orchestrate/{sid}/continue` with `approve` or `refine`

### Tabs
`page.tsx` keeps an array of `TabSession` objects. All tabs render simultaneously with `display:none` for inactive ones — this keeps orchestrator SSE streams alive when switching tabs.

### HTML report renderer
`backend/html_report_builder.py` produces a **standalone storyboarded HTML report**:
- 7 scrolling sections (Executive Snapshot → Strategic Implications)
- Cinematic hero, sticky nav, scroll progress bar
- KPI flip cards, animated bars, modals
- "Why This Matters" context setters, "What's Next" transition banners
- Section-specific verbatim quotes
- Exported via `GET /session/{sid}/export/html-report`

### PPTX renderer
`backend/pptx_builder.py` generates a polished multi-slide PPTX:
- Title slide, executive summary, findings with evidence, statistics, recommendations, appendix
- Purple/navy theme, Calibri fonts

---

## 7. Code structure

```
ci-studio/
├── backend/
│   ├── main.py                  # FastAPI app, all endpoints, session mgmt
│   ├── orchestrator.py          # Agentic ReAct loop (Opus + tool_use)
│   ├── orchestrator_endpoint.py # POST /orchestrate streaming endpoint
│   ├── report_types/            # Skill definitions (Pharma SI, Gen Z, XAI)
│   ├── skill_registry.py        # Manages skills + uploaded JSON skills
│   ├── skill_memory.py          # Learns from past runs
│   ├── template_library.py      # HTML report templates
│   ├── methodology.py           # AD + Monisha 19-step workflows
│   ├── mcp_registry.py          # Connector definitions
│   ├── connectors/              # Real working connectors
│   │   ├── reddit.py            # praw-based
│   │   ├── news_api.py          # newsapi.org
│   │   └── base.py              # DataConnector ABC
│   ├── design_connector.py      # Brand theme application
│   ├── html_report_builder.py   # Storyboarded HTML report
│   ├── pptx_builder.py          # PowerPoint export
│   ├── data_snapshot.py         # Persistence snapshot system
│   ├── demo_runs.py             # 3 pre-baked demo sessions
│   ├── supabase_client.py       # Supabase + JWT verification
│   ├── auth.py                  # FastAPI auth dependencies
│   ├── db.py                    # Postgres-backed storage
│   ├── db_schema.sql            # Postgres schema (run in Supabase)
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Main app shell, tab state, sidebar
│   │   ├── layout.tsx           # Root layout, AuthProvider
│   │   ├── globals.css          # Design system, fonts, gradients
│   │   ├── login/page.tsx       # Magic link login form
│   │   ├── auth/callback/route.ts  # OAuth callback handler
│   │   ├── components/
│   │   │   ├── Sidebar.tsx              # Workspace + Skills + Connectors + Knowledge
│   │   │   ├── StudioView.tsx           # Agents picker grid
│   │   │   ├── AgentInspectorModal.tsx  # Workspace UI (pipeline + details)
│   │   │   ├── AgentWorkspace.tsx       # Re-exports AgentInspectorModal
│   │   │   ├── AgentTabBar.tsx          # Browser-style tabs
│   │   │   ├── CompareView.tsx          # Side-by-side run comparison
│   │   │   ├── WorkbenchTab.tsx         # Tagged data table
│   │   │   ├── ExportTab.tsx            # Export options
│   │   │   ├── RunHistory.tsx           # Past runs list
│   │   │   ├── UserMenu.tsx             # Avatar + sign out
│   │   │   └── AuthProvider.tsx         # Supabase session context
│   │   └── lib/
│   │       ├── api.ts           # All backend API functions
│   │       └── supabase/
│   │           ├── client.ts    # Browser client
│   │           └── server.ts    # Server client
│   ├── proxy.ts                 # Next 16 middleware — currently AUTH DISABLED
│   ├── package.json
│   └── next.config.ts
│
├── render.yaml                  # Render Blueprint for backend
├── DEPLOY.md                    # Original deployment guide
└── HANDOVER.md                  # This file
```

---

## 8. Database schema (when Supabase enabled)

See `backend/db_schema.sql`. Tables:
- `workspaces` — one per user
- `sessions` — agent runs, JSONB data column holds raw + analyzed data
- `runs` — tagging run metadata
- `mcp_configs` — per-user connector configs (API keys encrypted at rest)
- `user_memory` — learned preferences
- `share_links` — public read-only tokens for reports

All tables have row-level security (RLS) policies: `auth.uid() = user_id`.

Bucket `uploads` (private) holds user-uploaded files when Supabase Storage is enabled.

---

## 9. Current state

### Working
- Agent picker, modal workspace, pipeline visualization
- Tabs (multi-agent parallel runs)
- Compare view
- Pharma SI tagging on Alexion HPP data (~5-7 min with GPT-4o-mini, MAX_WORKERS=30)
- HTML report export (storyboarded, 7 sections)
- PPTX export
- CSV / XLSX export
- Memory accumulation across runs
- Persistent snapshot (sessions survive Render restarts)
- 3 pre-baked demo runs (`/demos/{demo_id}/load`)
- Reddit + News API connectors
- Prod deploy on ci.alphametricx.com via Vercel + InfoVision-Agentic-AI/ci-studio

### Disabled / not working yet
- **Auth gate** — `proxy.ts` currently lets all requests through (disabled while ZeptoMail SMTP debugging finishes)
- **Backend auth** — Supabase env vars removed from Render; backend in anonymous mode
- **Canva integration** — UI built but no API connection (need Canva Enterprise, user has Pro only)
- **Other connectors** — Brandwatch, Meltwater, Sprinklr, Talkwalker, Twitter, Meta, InfoVision API are all UI placeholders
- **Share links** — backend endpoint built, no frontend "Share" button yet

### Known issues
- **Supabase magic link** — was hitting rate limit (4/hour); switched to ZeptoMail SMTP but not fully tested end-to-end at handover
- **Email "Stuck at sending"** — needs Supabase Auth log inspection to confirm SMTP creds
- **Session data wipes** — sessions are scoped by user; with auth disabled, all sessions land under `local-anon-user`
- **Report quality** — improved with rewritten prompt but still falls short of human-crafted reports from InfoVision (sample provided as reference)

---

## 10. To re-enable auth (when ready)

1. Restore env vars in Render: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
2. In `frontend/proxy.ts`, restore the original middleware logic (git history has it, commit `8c0d28b` before "Disable auth gate temporarily")
3. Verify SMTP works by sending a test magic link to your own email
4. Run `backend/db_schema.sql` in Supabase SQL editor (if not already)
5. Create `uploads` bucket (private) in Supabase Storage
6. Redeploy both frontend and backend

---

## 11. Cost & limits

| Service | Cost | Limits |
|---------|------|--------|
| Render starter plan | $7/mo | Always-on, 0.5 CPU, 512MB RAM |
| Vercel free | $0 | 100GB bandwidth/mo, fine for the team |
| Supabase free | $0 | 500MB DB, 1GB storage, 50k MAU |
| ZeptoMail | Paid sub | Per email pricing, no rate limit on transactional |
| OpenAI gpt-4o-mini | ~$0.15 per 1M input tokens | Pay-as-you-go |
| Anthropic Opus | ~$15 per 1M input tokens | Pay-as-you-go, big cost driver — used only for orchestrator + report gen |

**Typical run cost** (Alexion HPP, 713 rows after dedup):
- ~$0.10 for tagging (GPT-4o-mini)
- ~$1.50 for orchestrator reasoning + report (Opus)
- **Total: ~$1.60 per run**

---

## 12. Roadmap (priority order)

### Immediate (next session)
- Finish auth wire-up (SMTP debug, re-enable middleware)
- Fix file upload to Supabase Storage (currently still local disk)
- Add "Share" button on report views

### Short-term (1-2 weeks)
- Build Canva integration once Enterprise account available
- More connectors (at least Twitter, since users will ask)
- Better LLM report quality — fine-tune prompt with real InfoVision reports as exemplars
- Workspace dashboard (list past sessions per user)

### Medium-term (1-2 months)
- Multi-tenancy: separate workspaces per client/project
- Audit log (every agent action logged)
- Custom skill creation UI (user defines fields, schema saves to registry)
- Brand kit upload (logo, colors, fonts) per workspace → auto-applied to reports
- Real-time collaboration (multiple analysts on same run via Supabase Realtime)

### Long-term
- Mobile-responsive UI
- Dark mode
- Webhook system (notify Slack/Teams on run completion)
- White-label for selling to other agencies
- On-prem option for enterprise clients with data residency requirements

---

## 13. Troubleshooting cookbook

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| Frontend shows `{}` | Wrong URL — hitting backend not frontend | Open the Vercel deployment URL, not API URL |
| `Internal Server Error` on Vercel | Missing env var | Check `NEXT_PUBLIC_SUPABASE_URL` + anon key set for Production |
| `Upload failed (401)` | Backend has SUPABASE_URL but no JWT sent | Remove SUPABASE_* env vars from Render OR re-enable frontend auth |
| Magic link "stuck at sending" | SMTP misconfigured | Check Supabase Auth Logs; verify SMTP creds (username is literally `emailapikey`) |
| Tagging slow / timeout | Concurrency too low | Set `MAX_WORKERS=30`, `BATCH_SIZE=15` in Render env |
| Session not found after restart | Snapshot didn't load | Check Render logs for `DATA_DIR active:` line and `snapshot.json` existence |
| Report shows 0 findings | LLM JSON parse failed | Check backend logs for "Statistical fallback after LLM error"; verify Anthropic API key |
| 404 on Vercel deploy | Root directory wrong or branch wrong | Settings → Root Directory = `frontend`, Production Branch = `main` |
| Build fails on Render | Missing dep | Check `backend/requirements.txt`, push fix |

---

## 14. Who to contact

- **Sikander Ahmed** — built this with Claude. Sikander.ahmed@geniaz.com
- **Emanuel Davidson** (Research Lead at InfoVision) — product owner, gets the final outputs
- **Monisha** + **AD** — SMEs reviewing analyst-quality of outputs
- **Claude (Anthropic)** — pair-programmed every line via Claude Code

---

## 15. Last commit reference

Final working commit on dev branch: `b9ca414` ("Disable auth gate temporarily")
Branch: `EmanGeniaz/Testing-CI:claude/relaxed-bell-I40xJ`

Mirrored to prod: `InfoVision-Agentic-AI/ci-studio:main` (force-pushed)

---

*End of handover.*
