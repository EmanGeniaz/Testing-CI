"""
HTML Report Builder — Storyboarded Interactive Intelligence Artefact.

Generates a fully storyboarded, tabbed, interactive HTML intelligence report
from tagged pharma social intelligence data. Implements the complete
Storyboard Intelligence Skill specification: cinematic hero, sticky nav with
tab buttons, section-by-section story flow, "What's Next" bottom banners,
KPI flip cards, animated bars, modals, context-setting callouts, reading
progress bar, and scroll-reveal animations — all in a single self-contained
HTML file.
"""

from __future__ import annotations

import html as _html
from collections import Counter
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA HELPERS (kept from original)
# ═══════════════════════════════════════════════════════════════════════════════

def _safe(text: Any) -> str:
    """HTML-escape a value, converting None / non-str to empty string."""
    if text is None:
        return ""
    return _html.escape(str(text))


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{count * 100 // total}%"


def _pct_float(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total * 100, 1)


def _top_n(counter: Counter, n: int = 10, min_count: int = 0) -> list[tuple[str, int]]:
    items = counter.most_common(n)
    if min_count > 0:
        items = [(k, v) for k, v in items if v >= min_count]
    return items


def _pick_verbatims(rows: list[dict], fields: list[str], max_count: int = 10, filter_field: str = "", filter_values: list[str] | None = None) -> list[dict]:
    """Select the most vivid verbatim quotes from the data, optionally filtered by a field."""
    candidates: list[dict] = []
    for row in rows:
        if row.get("error"):
            continue
        if filter_field and filter_values:
            val = str(row.get(filter_field, "")).strip()
            if val not in filter_values:
                continue
        for field in fields:
            text = str(row.get(field, "")).strip()
            if text and len(text) > 40:
                candidates.append({
                    "text": text,
                    "reporter": row.get("reporter_type", "Patient"),
                    "platform": row.get("platform") or row.get("Platform") or "Online",
                    "stage": row.get("stage", ""),
                    "theme": row.get("theme", ""),
                    "concern": row.get("concern", ""),
                    "unmet_need": row.get("unmet_need", ""),
                    "qol_impact": row.get("qol_impact", ""),
                })
    # Sort by length (longer = more descriptive), deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for c in sorted(candidates, key=lambda x: len(x["text"]), reverse=True):
        key = c["text"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:max_count]


# ═══════════════════════════════════════════════════════════════════════════════
#  STATISTICS COLLECTOR (kept from original)
# ═══════════════════════════════════════════════════════════════════════════════

def _collect_stats(tagged_data: list[dict]) -> dict:
    """Compute all distributions from the tagged rows."""
    stats: dict = {
        "total": len(tagged_data),
        "errors": 0,
        "platforms": Counter(),
        "themes": Counter(),
        "stages": Counter(),
        "unmet_needs": Counter(),
        "concerns": Counter(),
        "qol_impacts": Counter(),
        "reporter_types": Counter(),
        "sentiments": Counter(),
    }

    for row in tagged_data:
        if row.get("error"):
            stats["errors"] += 1
            continue

        # Platform — try several common column names
        plat = (row.get("platform") or row.get("Platform")
                or row.get("source_platform") or "")
        if plat:
            stats["platforms"][str(plat).strip()] += 1

        if row.get("theme"):
            stats["themes"][row["theme"]] += 1
        if row.get("stage"):
            stats["stages"][row["stage"]] += 1
        if row.get("unmet_need"):
            stats["unmet_needs"][row["unmet_need"]] += 1
        if row.get("concern"):
            stats["concerns"][row["concern"]] += 1
        if row.get("qol_impact"):
            stats["qol_impacts"][row["qol_impact"]] += 1
        if row.get("reporter_type"):
            stats["reporter_types"][row["reporter_type"]] += 1
        if row.get("sentiment"):
            stats["sentiments"][row["sentiment"]] += 1

    stats["valid"] = stats["total"] - stats["errors"]
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
#  DESIGN SYSTEM CSS — from Storyboarding Skill spec
# ═══════════════════════════════════════════════════════════════════════════════

_CSS = r"""
/* ── ROOT TOKENS ─────────────────────────────────────── */
:root {
  --bg: #FAFBFD;
  --bg2: #F4F6FB;
  --card: #FFFFFF;
  --line: #EAEEF5;
  --ink: #0E1320;
  --ink2: #374151;
  --ink3: #6B7280;
  --ink4: #9CA3AF;
  --pos: #10B981;
  --neu: #F59E0B;
  --neg: #EF4444;
  --shadow-sm: 0 1px 3px rgba(14,19,32,.05), 0 1px 8px rgba(14,19,32,.04);
  --shadow: 0 4px 18px rgba(14,19,32,.07), 0 1px 4px rgba(14,19,32,.04);
  --shadow-lg: 0 20px 50px rgba(14,19,32,.11), 0 4px 14px rgba(14,19,32,.05);
  --r: 18px;
  --r-sm: 12px;
  --brand-1: #6366F1;
  --brand-2: #8B5CF6;
  --brand-3: #EC4899;
}

/* ── RESET ───────────────────────────────────────────── */
*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--ink);
  min-height:100vh; line-height:1.5; -webkit-font-smoothing:antialiased; }

/* ── READING PROGRESS BAR ────────────────────────────── */
.prog-track { position:fixed; top:0; left:0; right:0; height:3px; z-index:300; pointer-events:none; }
.prog-fill { height:100%; width:0%; background:linear-gradient(90deg,var(--brand-1),var(--brand-3));
  transition:width .5s cubic-bezier(.22,1,.36,1); box-shadow:0 0 16px rgba(99,102,241,.45); }

/* ── STICKY NAV + TAB BAR ────────────────────────────── */
.nav-wrap { position:sticky; top:0; z-index:50; background:rgba(250,251,253,.88);
  backdrop-filter:blur(24px) saturate(180%); border-bottom:1px solid var(--line); }
.nav-inner { max-width:1440px; margin:0 auto; padding:0 56px;
  display:flex; align-items:center; gap:24px; height:70px; }
.brand { display:flex; align-items:center; gap:12px; }
.brand-mark { width:36px; height:36px; border-radius:10px;
  background:linear-gradient(135deg,var(--brand-1),var(--brand-2));
  display:flex; align-items:center; justify-content:center;
  font-family:'Space Grotesk',sans-serif; font-weight:800; font-size:14px; color:#fff; }
.brand-text .brand-name { font-family:'Space Grotesk',sans-serif; font-size:14px;
  font-weight:700; color:var(--ink); line-height:1.2; }
.brand-text .brand-sub { font-size:10px; color:var(--ink3); letter-spacing:.06em; }
.tab-bar { display:flex; align-items:center; gap:4px; margin-left:auto; flex-wrap:wrap; }
.tab { padding:9px 16px; border-radius:11px; font-size:13px; font-weight:600;
  color:#475569; cursor:pointer; display:flex; align-items:center; gap:7px;
  border:1px solid transparent; background:transparent;
  transition:all .25s cubic-bezier(.22,1,.36,1); }
.tab:hover { color:#0F172A; background:rgba(99,102,241,.06); }
.tab .tdot { width:8px; height:8px; border-radius:50%; background:var(--brand-1); }
.tab.active { background:#0F172A; color:#fff; box-shadow:0 6px 18px rgba(15,23,42,.18); }
.tab.active .tdot { background:#fff !important; }

/* ── HERO BANNER ─────────────────────────────────────── */
.hero { position:relative; width:100%; height:460px; overflow:hidden;
  background:#060A14; border-bottom:1px solid var(--line); isolation:isolate; }
.hero-overlay { position:absolute; inset:0; z-index:1;
  background:linear-gradient(180deg,rgba(6,10,20,.55) 0%,rgba(6,10,20,.18) 35%,
    rgba(6,10,20,.28) 65%,rgba(6,10,20,.72) 100%); }
.hero-grid { position:absolute; inset:0; z-index:2;
  background-image: linear-gradient(rgba(200,210,255,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(200,210,255,.04) 1px,transparent 1px);
  background-size:52px 52px;
  mask-image:radial-gradient(900px 500px at 50% 50%,#000 20%,transparent 100%);
  -webkit-mask-image:radial-gradient(900px 500px at 50% 50%,#000 20%,transparent 100%); }
.hero-inner { position:relative; z-index:3; max-width:1440px; margin:0 auto;
  padding:52px 56px 0; height:100%; display:flex; flex-direction:column;
  justify-content:space-between; }
.hero-top { display:flex; align-items:center; justify-content:space-between; }
.hero-eyebrow { display:inline-flex; align-items:center; gap:10px;
  font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:rgba(226,232,240,.7); }
.hero-eyebrow .dot { width:8px; height:8px; border-radius:50%; background:#10B981;
  box-shadow:0 0 0 4px rgba(16,185,129,.3); }
.hero-chips { display:flex; gap:10px; }
.hero-chip { background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.18);
  backdrop-filter:blur(8px); padding:5px 16px; border-radius:24px;
  font-size:11px; font-weight:600; color:#fff; letter-spacing:.04em; }
.hero-center { padding-bottom:52px; }
.hero-title { font-family:'Space Grotesk',sans-serif; font-size:clamp(40px,5.5vw,68px);
  font-weight:800; line-height:1.02; letter-spacing:-.035em;
  background:linear-gradient(135deg,#FFFFFF 0%,#C7D2FE 50%,#F5D0FE 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; margin-bottom:16px; }
.hero-sub { font-size:14px; color:rgba(226,232,240,.65); line-height:1.7;
  max-width:580px; margin-bottom:24px; }
.hero-stats { display:flex; border-radius:16px; background:rgba(10,15,30,.55);
  backdrop-filter:blur(24px); border:1px solid rgba(255,255,255,.13); overflow:hidden;
  width:fit-content; box-shadow:0 8px 36px rgba(0,0,0,.28); }
.hstat { padding:18px 28px; border-right:1px solid rgba(255,255,255,.09); }
.hstat:last-child { border-right:none; }
.hstat .v { font-family:'Space Grotesk',sans-serif; font-size:28px; font-weight:700;
  color:#fff; letter-spacing:-.02em; line-height:1; }
.hstat .l { font-size:10px; font-weight:600; color:rgba(226,232,240,.6);
  letter-spacing:.09em; text-transform:uppercase; margin-top:6px; }

/* ── TAB PANELS ──────────────────────────────────────── */
.tab-panel { display:block; margin-bottom:60px; }
.tab-panel .page { max-width:1440px; margin:0 auto; padding:36px 56px 20px; }
@keyframes tabIn { 0%{opacity:0;transform:translateY(10px);}100%{opacity:1;transform:translateY(0);} }
.page { max-width:1440px; margin:0 auto; padding:36px 56px 80px; }

/* ── SECTION BANNER ──────────────────────────────────── */
.tbanner { position:relative; width:100%; height:220px; border-radius:22px;
  overflow:hidden; margin-bottom:30px; box-shadow:var(--shadow); }
.tbanner .bg-overlay { position:absolute; inset:0;
  background:linear-gradient(135deg,rgba(15,23,42,.05) 0%,rgba(15,23,42,.20) 100%); }
.tbanner .anim-layer { position:absolute; inset:0; overflow:hidden; }
.tbanner .text-layer { position:absolute; inset:0; z-index:3;
  padding:32px 40px; display:flex; flex-direction:column; justify-content:flex-end; }
.tbanner .eyebrow { display:inline-flex; align-items:center; gap:8px;
  backdrop-filter:blur(12px); padding:5px 12px; border-radius:24px;
  width:fit-content; font-size:10px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:#fff; background:rgba(255,255,255,.15); }
.tbanner h2 { font-size:32px; font-weight:800; color:#fff; letter-spacing:-.025em;
  margin-top:12px; text-shadow:0 4px 20px rgba(0,0,0,.25);
  font-family:'Space Grotesk',sans-serif; }
.tbanner .tsub { font-size:13px; color:rgba(255,255,255,.90); margin-top:6px;
  font-weight:400; text-shadow:0 2px 10px rgba(0,0,0,.18); max-width:640px; }
.tbanner .tbadges { display:flex; gap:10px; margin-top:16px; }
.tbanner .tbadge { padding:5px 12px; border-radius:24px;
  background:rgba(255,255,255,.90); backdrop-filter:blur(12px);
  font-size:11px; font-weight:600; color:#0F172A; }

/* Banner palettes */
.b-dark { background:linear-gradient(135deg, #1E293B, #0F172A, #312E81); }
.b-brand1 { background:linear-gradient(135deg, #4338CA, #6366F1, #818CF8); }
.b-brand2 { background:linear-gradient(135deg, #7C3AED, #8B5CF6, #A78BFA); }
.b-brand3 { background:linear-gradient(135deg, #BE2BBB, #EC4899, #F9A8D4); }
.b-green { background:linear-gradient(135deg, #064E3B, #059669, #34D399); }
.b-red { background:linear-gradient(135deg, #450A0A, #DC2626, #F97316); }
.b-gold { background:linear-gradient(135deg, #78350F, #C8973A, #FDE68A); }
.b-teal { background:linear-gradient(135deg, #0F4C5C, #0891B2, #22D3EE); }

/* ── CONTEXT SETTER ──────────────────────────────────── */
.ctx-setter { display:flex; align-items:flex-start; gap:16px; padding:18px 24px;
  border-radius:14px; border-left:4px solid var(--brand-1); margin-bottom:28px; }
.ctx-setter.neutral { background:linear-gradient(135deg,#F8FAFF,#EEF2FF); border-left-color:#6366F1; }
.ctx-setter.positive { background:linear-gradient(135deg,#F0FDF4,#DCFCE7); border-left-color:var(--pos); }
.ctx-setter.risk { background:linear-gradient(135deg,#FFF5F5,#FEE2E2); border-left-color:var(--neg); }
.ctx-setter.warning { background:linear-gradient(135deg,#FFFBEB,#FEF3DC); border-left-color:var(--neu); }
.ctx-icon { width:36px; height:36px; border-radius:10px; display:flex;
  align-items:center; justify-content:center; flex-shrink:0; font-size:18px;
  background:rgba(99,102,241,.1); }
.ctx-text .ctx-why { font-size:10px; font-weight:700; letter-spacing:.16em;
  text-transform:uppercase; color:var(--brand-1); margin-bottom:5px; }
.ctx-text .ctx-line { font-size:13px; font-weight:500; color:#0F172A; line-height:1.65; }

/* ── KPI FLIP CARDS ──────────────────────────────────── */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:26px; }
.kpi { position:relative; background:#fff; border-radius:var(--r); border:1px solid var(--line);
  padding:22px 24px; box-shadow:var(--shadow-sm); cursor:pointer; perspective:1200px;
  height:144px; transition:all .3s ease; }
.kpi:hover { box-shadow:var(--shadow); transform:translateY(-2px); }
.kpi-flip { position:relative; width:100%; height:100%; transform-style:preserve-3d;
  transition:transform .65s cubic-bezier(.22,1,.36,1); }
.kpi.flipped .kpi-flip { transform:rotateY(180deg); }
.kpi-front, .kpi-back { position:absolute; inset:0; backface-visibility:hidden;
  -webkit-backface-visibility:hidden; display:flex; flex-direction:column;
  justify-content:space-between; }
.kpi-back { transform:rotateY(180deg); }
.kpi-back p { font-size:12px; color:#374151; line-height:1.55; margin:0; }
.kpi-back .blbl { font-size:10px; font-weight:700; letter-spacing:.12em;
  color:var(--brand-1); text-transform:uppercase; margin-bottom:8px; }
.kpi .l { font-size:10px; font-weight:600; letter-spacing:.09em;
  text-transform:uppercase; color:#94A3B8; }
.kpi .v { font-family:'Space Grotesk',sans-serif; font-size:32px; font-weight:700;
  color:#0F172A; letter-spacing:-.02em; line-height:1; }
.kpi .delta { display:flex; align-items:center; gap:6px; font-size:12px; font-weight:600; }
.kpi .delta.up { color:var(--pos); } .kpi .delta.dn { color:var(--neg); }
.kpi .delta.flat { color:var(--neu); }
.kpi.k-accent::after { content:''; position:absolute; top:0; left:0; right:0; height:3px;
  border-radius:var(--r) var(--r) 0 0;
  background:linear-gradient(90deg,var(--ac1,#6366F1),var(--ac2,#8B5CF6)); }
.flip-hint { position:absolute; top:14px; right:14px; font-size:9px;
  color:#CBD5E1; font-weight:600; }

/* ── WHAT'S NEXT BANNER ──────────────────────────────── */
.whats-next { position:relative; background:linear-gradient(135deg,#0F172A 0%,#1E1B4B 45%,#312E81 100%);
  border-radius:22px; padding:38px 44px; color:#fff; overflow:hidden; margin-top:40px; }
.whats-next::before { content:''; position:absolute; top:-40%; right:-8%; width:520px;height:520px;
  background:radial-gradient(circle,rgba(200,151,58,.22),transparent 60%); pointer-events:none; }
.whats-next::after { content:''; position:absolute; bottom:-40%; left:-8%; width:440px;height:440px;
  background:radial-gradient(circle,rgba(99,102,241,.22),transparent 60%); pointer-events:none; }
.wn-inner { position:relative; display:grid; grid-template-columns:1fr 1.7fr;
  gap:40px; align-items:center; }
.wn-eyebrow { display:inline-flex; align-items:center; gap:8px; padding:5px 13px;
  border-radius:24px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.18);
  font-size:10px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; margin-bottom:14px; }
.wn-eyebrow .icon { width:8px; height:8px; border-radius:50%; background:#10B981;
  box-shadow:0 0 0 4px rgba(16,185,129,.28); }
.wn-title { font-size:30px; font-weight:800; letter-spacing:-.025em;
  line-height:1.08; margin-bottom:10px; font-family:'Space Grotesk',sans-serif; }
.wn-sub { font-size:13px; color:rgba(255,255,255,.70); line-height:1.6; margin:0; }
.wn-actions { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.wn-action { padding:16px 18px; border-radius:14px; background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.14); cursor:pointer; transition:all .25s ease; }
.wn-action:hover { background:rgba(255,255,255,.14); transform:translateY(-2px);
  border-color:rgba(255,255,255,.28); }
.wn-action .wnum { font-family:'Space Grotesk',sans-serif; font-size:13px; font-weight:700;
  color:#FDE68A; letter-spacing:.06em; margin-bottom:6px; }
.wn-action h5 { font-size:13px; font-weight:700; color:#fff; margin-bottom:5px; }
.wn-action p { font-size:11px; color:rgba(255,255,255,.65); line-height:1.5; margin:0; }
.wn-cta-row { margin-top:22px; padding-top:22px;
  border-top:1px solid rgba(255,255,255,.12); display:flex; justify-content:flex-end; }
.wn-cta { display:inline-flex; align-items:center; gap:14px; padding:13px 22px;
  border-radius:999px; background:#fff; color:#0F172A; border:none;
  font-family:'Inter',sans-serif; font-weight:700; cursor:pointer;
  box-shadow:0 8px 24px rgba(0,0,0,.18); transition:all .3s cubic-bezier(.22,1,.36,1);
  position:relative; overflow:hidden; }
.wn-cta::before { content:''; position:absolute; inset:0;
  background:linear-gradient(90deg,transparent,rgba(99,102,241,.12),transparent);
  transform:translateX(-100%); transition:transform .6s ease; }
.wn-cta:hover { transform:translateX(4px); box-shadow:0 14px 36px rgba(0,0,0,.26); }
.wn-cta:hover::before { transform:translateX(100%); }
.wn-cta-lbl { font-size:10px; font-weight:700; letter-spacing:.16em; color:var(--brand-1); }
.wn-cta-name { font-size:14px; font-weight:700; color:#0F172A; padding:0 6px;
  position:relative; }
.wn-cta-name::before { content:''; position:absolute; left:0; top:50%; height:13px;
  width:1px; background:rgba(15,23,42,.18); transform:translateY(-50%); }
.wn-cta svg { color:var(--brand-1); transition:transform .3s ease; }
.wn-cta:hover svg { transform:translateX(4px); }

/* ── MODAL ────────────────────────────────────────────── */
.modal-bg { position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:200;
  display:flex; justify-content:center; align-items:center;
  backdrop-filter:blur(4px); opacity:0; pointer-events:none;
  transition:opacity .3s ease; }
.modal-bg.open { opacity:1; pointer-events:all; }
.modal-box { background:#fff; border-radius:var(--r); max-width:600px; width:90%;
  max-height:80vh; overflow-y:auto; box-shadow:0 24px 64px rgba(99,102,241,.2);
  padding:32px; position:relative; animation:modalIn 0.3s ease-out; }
@keyframes modalIn { from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);} }
.modal-close { position:absolute; top:16px; right:16px; width:32px; height:32px;
  border-radius:8px; border:none; background:var(--bg2); cursor:pointer;
  font-size:18px; display:flex; align-items:center; justify-content:center;
  color:var(--ink3); transition:all .15s; }
.modal-close:hover { background:var(--brand-1); color:#fff; }
.modal-tag { font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color:var(--brand-1); margin-bottom:6px; }
.modal-title { font-family:'Space Grotesk',sans-serif; font-size:20px; font-weight:700;
  color:var(--ink); margin-bottom:16px; }
.modal-body p { font-size:13px; color:var(--ink2); line-height:1.7; margin-bottom:12px; }
.modal-body strong { color:var(--ink); }
.modal-stats { display:flex; gap:16px; margin-bottom:16px; }
.modal-stat { padding:12px 16px; background:var(--bg2); border-radius:var(--r-sm); flex:1; }
.modal-stat .mv { font-family:'Space Grotesk',sans-serif; font-size:22px; font-weight:700;
  color:var(--brand-1); }
.modal-stat .ml { font-size:10px; font-weight:600; color:var(--ink3); text-transform:uppercase;
  letter-spacing:.08em; margin-top:2px; }

/* ── CONTENT COMPONENTS ──────────────────────────────── */
.card { background:#fff; border-radius:var(--r); padding:24px; box-shadow:var(--shadow);
  border:1px solid var(--line); transition:all .2s; margin-bottom:20px; }
.card:hover { box-shadow:var(--shadow-lg); }
.card-title { font-family:'Space Grotesk',sans-serif; font-size:15px; font-weight:700;
  color:var(--ink); margin-bottom:4px; display:flex; align-items:center; justify-content:space-between; }
.card-sub { font-size:11px; color:var(--ink3); margin-bottom:18px; }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:20px; }
.grid-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:18px; margin-bottom:20px; }

/* Bar rows */
.bar-row { display:flex; align-items:center; gap:10px; margin-bottom:9px; }
.bar-lbl { font-size:12px; color:var(--ink2); min-width:140px; text-align:right; font-weight:500; }
.bar-track { flex:1; background:var(--bg2); border-radius:6px; height:10px; overflow:hidden; }
.bar-fill { height:100%; border-radius:6px; transition:width 1.2s cubic-bezier(.22,1,.36,1); }
.bar-val { font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:500;
  color:var(--ink); min-width:70px; }

/* Quote cards */
.quote-card { background:linear-gradient(135deg,var(--brand-1),var(--brand-2));
  border-radius:var(--r-sm); padding:18px 20px; color:#fff; margin-bottom:12px; }
.quote-card:nth-child(even) { background:linear-gradient(135deg,var(--brand-2),var(--brand-3)); }
.quote-text { font-size:13px; font-style:italic; line-height:1.65; margin-bottom:10px; }
.quote-meta { font-size:10px; font-weight:700; opacity:.75; letter-spacing:.06em; text-transform:uppercase; }

/* Journey grid */
.journey-wrap { display:grid; gap:0; }
.journey-stage { padding:22px 18px; position:relative; border-right:1px solid var(--line);
  background:#fff; transition:background .2s; }
.journey-stage:last-child { border-right:none; }
.journey-stage:hover { background:var(--bg2); }
.journey-stage::after { content:'\2192'; position:absolute; right:-14px; top:50%;
  transform:translateY(-50%); color:var(--ink4); font-size:16px; z-index:2; }
.journey-stage:last-child::after { display:none; }
.stage-label { font-size:10px; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
  color:var(--brand-1); margin-bottom:8px; }
.stage-n { font-family:'Space Grotesk',sans-serif; font-size:28px; font-weight:800;
  color:var(--ink); line-height:1; margin-bottom:4px; }
.stage-pct { font-size:11px; color:var(--ink3); margin-bottom:10px; }
.stage-frictions { list-style:none; }
.stage-frictions li { font-size:11.5px; color:var(--ink2); padding:3px 0;
  display:flex; gap:6px; align-items:flex-start; }
.stage-frictions li::before { content:'\26A0'; font-size:11px; color:var(--neg);
  flex-shrink:0; }

/* Strategy cards */
.strat-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:28px; }
.strat-card { background:#fff; border-radius:var(--r); padding:22px; box-shadow:var(--shadow);
  border:1px solid var(--line); display:flex; gap:16px; transition:all .2s; }
.strat-card:hover { transform:translateY(-2px); box-shadow:var(--shadow-lg); }
.strat-num { width:40px; height:40px; border-radius:12px;
  background:linear-gradient(135deg,var(--brand-1),var(--brand-2));
  display:flex; align-items:center; justify-content:center;
  font-family:'Space Grotesk',sans-serif; font-size:15px; font-weight:800;
  color:#fff; flex-shrink:0; }
.strat-title { font-size:14px; font-weight:700; color:var(--ink); margin-bottom:5px; }
.strat-text { font-size:12px; color:var(--ink2); line-height:1.6; }
.strat-evidence { margin-top:8px; font-size:11px; font-weight:600; color:var(--brand-1);
  background:rgba(99,102,241,.08); padding:4px 10px; border-radius:6px; display:inline-block; }

/* Insight button */
.insight-btn { font-size:10px; font-weight:700; padding:5px 12px; border-radius:20px;
  background:rgba(99,102,241,.08); color:var(--brand-1); border:1px solid rgba(99,102,241,.18);
  cursor:pointer; transition:all .18s; white-space:nowrap;
  display:inline-flex; align-items:center; gap:4px; }
.insight-btn:hover { background:var(--brand-1); color:#fff; border-color:transparent; }

/* ── SCROLL REVEAL ───────────────────────────────────── */
.reveal { opacity:0; transform:translateY(20px); transition:opacity .7s ease,transform .7s ease; }
.reveal.vis { opacity:1; transform:translateY(0); }
.reveal.d1 { transition-delay:.1s; }
.reveal.d2 { transition-delay:.2s; }
.reveal.d3 { transition-delay:.3s; }

/* ── FLOAT UP (particles) ────────────────────────────── */
@keyframes floatUp {
  0% { transform:translateY(260px) scale(0); opacity:0; }
  10% { opacity:.5; }
  80% { opacity:.3; }
  100% { transform:translateY(-60px) scale(1.2); opacity:0; }
}

/* ── RESPONSIVE ──────────────────────────────────────── */
@media (max-width:900px) {
  .nav-inner { padding:0 20px; }
  .page { padding:20px; }
  .hero-inner { padding:32px 20px 0; }
  .hero-title { font-size:32px !important; }
  .kpi-grid { grid-template-columns:1fr 1fr; }
  .grid-2 { grid-template-columns:1fr; }
  .strat-grid { grid-template-columns:1fr; }
  .wn-inner { grid-template-columns:1fr; }
  .wn-actions { grid-template-columns:1fr; }
  .tab { padding:6px 10px; font-size:11px; }
}

/* ── PRINT ───────────────────────────────────────────── */
@media print {
  body { background:#fff; }
  .prog-track, .nav-wrap { display:none; }
  .tab-panel { display:block !important; page-break-inside:avoid; }
  .tbanner, .hero, .whats-next, .strat-num, .bar-fill, .kpi.k-accent::after {
    -webkit-print-color-adjust:exact; print-color-adjust:exact; }
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB DEFINITIONS — section metadata per tab
# ═══════════════════════════════════════════════════════════════════════════════

_TAB_META = [
    {"id": "tab1", "label": "Executive Snapshot", "num": "01", "banner_cls": "b-dark",
     "icon_emoji": "&#128202;",
     "particle_colors": "['rgba(99,102,241,.4)','rgba(139,92,246,.3)','rgba(255,255,255,.15)']"},
    {"id": "tab2", "label": "Platform & Stakeholder", "num": "02", "banner_cls": "b-brand1",
     "icon_emoji": "&#128225;",
     "particle_colors": "['rgba(67,56,202,.4)','rgba(99,102,241,.3)','rgba(255,255,255,.12)']"},
    {"id": "tab3", "label": "Theme Intelligence", "num": "03", "banner_cls": "b-brand2",
     "icon_emoji": "&#127991;",
     "particle_colors": "['rgba(124,58,237,.4)','rgba(139,92,246,.3)','rgba(255,255,255,.12)']"},
    {"id": "tab4", "label": "Patient Journey", "num": "04", "banner_cls": "b-brand3",
     "icon_emoji": "&#128506;",
     "particle_colors": "['rgba(190,43,187,.4)','rgba(236,72,153,.3)','rgba(255,255,255,.12)']"},
    {"id": "tab5", "label": "Unmet Needs", "num": "05", "banner_cls": "b-green",
     "icon_emoji": "&#128138;",
     "particle_colors": "['rgba(6,78,59,.4)','rgba(5,150,105,.3)','rgba(255,255,255,.12)']"},
    {"id": "tab6", "label": "Concerns & QoL", "num": "06", "banner_cls": "b-red",
     "icon_emoji": "&#9888;",
     "particle_colors": "['rgba(69,10,10,.4)','rgba(220,38,38,.3)','rgba(255,255,255,.12)']"},
    {"id": "tab7", "label": "Strategic Implications", "num": "07", "banner_cls": "b-gold",
     "icon_emoji": "&#127919;",
     "particle_colors": "['rgba(120,53,15,.4)','rgba(200,151,58,.3)','rgba(255,255,255,.12)']"},
]

_BAR_COLORS = [
    "var(--brand-1)", "var(--brand-2)", "var(--brand-3)",
    "var(--pos)", "#0891B2", "var(--neu)", "#6366F1", "#8B5CF6",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPONENT BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_section_banner(tab_id: str, num: str, title: str, subtitle: str,
                          banner_cls: str, badges: list[str]) -> str:
    """Section banner with colour gradient and animated particle layer."""
    badge_html = "".join(f'<span class="tbadge">{_safe(b)}</span>' for b in badges)
    return f"""
    <div class="tbanner {banner_cls}">
      <div class="bg-overlay"></div>
      <div class="anim-layer" id="{tab_id}Particles"></div>
      <div class="text-layer">
        <div class="eyebrow">{_safe(num)} &middot; {_safe(title)}</div>
        <h2>{_safe(title)}</h2>
        <p class="tsub">{_safe(subtitle)}</p>
        <div class="tbadges">{badge_html}</div>
      </div>
    </div>"""


def _build_context_setter(emoji: str, lead: str, body: str,
                          style: str = "neutral") -> str:
    """Mandatory context setter — 'Why This Intelligence Matters'."""
    return f"""
    <div class="ctx-setter {style} reveal">
      <div class="ctx-icon">{emoji}</div>
      <div class="ctx-text">
        <div class="ctx-why">Why This Intelligence Matters</div>
        <div class="ctx-line"><strong>{lead}</strong> {body}</div>
      </div>
    </div>"""


def _build_kpi_card(label: str, value: str, data_count: int,
                    delta_text: str, delta_cls: str,
                    back_text: str,
                    ac1: str = "#6366F1", ac2: str = "#8B5CF6") -> str:
    """Single KPI flip card."""
    return f"""
    <div class="kpi k-accent reveal" data-flip style="--ac1:{ac1};--ac2:{ac2};">
      <div class="kpi-flip">
        <div class="kpi-front">
          <div class="l">{_safe(label)}</div>
          <div class="v" data-count="{data_count}">0</div>
          <div class="delta {delta_cls}">{_safe(delta_text)}</div>
        </div>
        <div class="kpi-back">
          <div class="blbl">What This Means</div>
          <p>{_safe(back_text)}</p>
        </div>
      </div>
      <div class="flip-hint">&#x21bb; flip</div>
    </div>"""


def _build_bar_rows(items: list[tuple[str, int]], total: int,
                    color: str = "var(--brand-1)") -> str:
    """Horizontal animated bar rows using data-w for animation."""
    if not items:
        return '<div style="padding:12px;color:var(--ink3);font-size:13px;">No data available.</div>'
    max_val = items[0][1] if items else 1
    parts: list[str] = []
    for label, count in items:
        bar_w = max(2, int(count / max_val * 100)) if max_val else 0
        pct = _pct(count, total)
        parts.append(
            f'<div class="bar-row reveal">'
            f'<div class="bar-lbl">{_safe(label)}</div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:0;background:{color};" data-w="{bar_w}%"></div>'
            f'</div>'
            f'<div class="bar-val">{count} &nbsp;({pct})</div>'
            f'</div>'
        )
    return "\n".join(parts)


def _build_quote_cards(verbatims: list[dict], max_cards: int = 5) -> str:
    """Styled verbatim quote cards."""
    parts: list[str] = []
    for v in verbatims[:max_cards]:
        meta_parts = [_safe(v.get("reporter", ""))]
        if v.get("platform"):
            meta_parts.append(_safe(v["platform"]))
        if v.get("stage"):
            meta_parts.append(_safe(v["stage"]))
        meta = " &middot; ".join([p for p in meta_parts if p])
        parts.append(
            f'<div class="quote-card reveal">'
            f'<div class="quote-text">&ldquo;{_safe(v["text"])}&rdquo;</div>'
            f'<div class="quote-meta">{meta}</div>'
            f'</div>'
        )
    return "\n".join(parts) if parts else '<div style="padding:12px;color:var(--ink3);font-size:13px;">No verbatim quotes available.</div>'


def _build_whats_next(title: str, subtitle: str,
                      actions: list[dict],
                      next_tab_id: str, next_tab_label: str,
                      is_last: bool = False) -> str:
    """What's Next banner — mandatory at bottom of every tab panel."""
    action_tiles = ""
    for a in actions[:4]:
        action_tiles += f"""
        <div class="wn-action" onclick="switchTab('{a['tab_id']}')">
          <div class="wnum">&rarr; {_safe(a.get('num', ''))}</div>
          <h5>{_safe(a.get('title', ''))}</h5>
          <p>{_safe(a.get('tease', ''))}</p>
        </div>"""

    cta_label = "RESTART" if is_last else "CONTINUE"
    arrow_svg = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
                 'stroke="currentColor" stroke-width="2.5">'
                 '<path d="M5 12h14M13 5l7 7-7 7"/></svg>')

    return f"""
    <div class="whats-next reveal">
      <div class="wn-inner">
        <div>
          <div class="wn-eyebrow"><span class="icon"></span>What&#39;s Next</div>
          <h3 class="wn-title">{_safe(title)}</h3>
          <p class="wn-sub">{_safe(subtitle)}</p>
        </div>
        <div>
          <div class="wn-actions">{action_tiles}</div>
          <div class="wn-cta-row">
            <button class="wn-cta" onclick="switchTab('{next_tab_id}')">
              <span class="wn-cta-lbl">{cta_label}</span>
              <span class="wn-cta-name">{_safe(next_tab_label)}</span>
              {arrow_svg}
            </button>
          </div>
        </div>
      </div>
    </div>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB PANEL BUILDERS — one function per tab
# ═══════════════════════════════════════════════════════════════════════════════

def _tab1_executive_snapshot(stats: dict) -> str:
    """Tab 1: Executive Snapshot — headline KPIs + context."""
    valid = stats["valid"]
    n_platforms = len(stats["platforms"])
    n_themes = len(stats["themes"])
    top_theme = _top_n(stats["themes"], 1)
    top_concern = _top_n(stats["concerns"], 1)
    top_unmet = _top_n(stats["unmet_needs"], 1)

    top_theme_name = top_theme[0][0] if top_theme else "N/A"
    top_theme_count = top_theme[0][1] if top_theme else 0
    top_concern_name = top_concern[0][0] if top_concern else "N/A"
    top_concern_count = top_concern[0][1] if top_concern else 0
    top_unmet_name = top_unmet[0][0] if top_unmet else "N/A"
    top_unmet_count = top_unmet[0][1] if top_unmet else 0

    banner = _build_section_banner(
        "tab1", "01", "Executive Snapshot",
        f"{valid} posts analysed across {n_platforms} platforms with {n_themes} distinct themes identified.",
        "b-dark",
        [f"{valid} Posts", f"{n_platforms} Platforms", f"{n_themes} Themes"]
    )

    ctx = _build_context_setter(
        "&#128202;",
        f"{valid} social intelligence posts were coded across {n_platforms} platforms.",
        f"The dominant theme is {_safe(top_theme_name)} ({_pct(top_theme_count, valid)} of posts), "
        f"while the top patient concern is {_safe(top_concern_name)} "
        f"and the leading unmet need is {_safe(top_unmet_name)}. "
        f"This executive view provides the strategic compass for all downstream analysis.",
        "neutral"
    )

    # KPI cards
    kpis = '<div class="kpi-grid">'
    kpis += _build_kpi_card(
        "Total Posts", str(valid), valid,
        f"{n_platforms} platforms", "flat",
        f"A base of {valid} coded posts provides a robust signal. "
        f"Coverage spans {n_platforms} platforms, giving breadth to the intelligence picture.",
        "#6366F1", "#8B5CF6"
    )
    kpis += _build_kpi_card(
        "Platforms", str(n_platforms), n_platforms,
        "Digital footprint", "flat",
        f"Conversations are distributed across {n_platforms} platforms. "
        f"This multi-platform spread indicates broad online discussion, "
        f"requiring platform-specific engagement strategies.",
        "#8B5CF6", "#EC4899"
    )
    kpis += _build_kpi_card(
        "Top Theme", _safe(top_theme_name), top_theme_count,
        f"{_pct(top_theme_count, valid)} of posts", "up",
        f"{_safe(top_theme_name)} dominates the thematic landscape at {_pct(top_theme_count, valid)}. "
        f"This concentration suggests a primary narrative that should be central "
        f"to brand messaging and medical communications strategy.",
        "#EC4899", "#F59E0B"
    )
    kpis += _build_kpi_card(
        "Top Concern", _safe(top_concern_name), top_concern_count,
        f"{_pct(top_concern_count, valid)} of posts", "dn",
        f"Patient concern about {_safe(top_concern_name)} leads at {_pct(top_concern_count, valid)}. "
        f"This signals an immediate need for educational materials, "
        f"HCP discussion guides, and proactive risk communications.",
        "#EF4444", "#F59E0B"
    )
    kpis += _build_kpi_card(
        "Top Unmet Need", _safe(top_unmet_name), top_unmet_count,
        f"{_pct(top_unmet_count, valid)} of posts", "dn",
        f"{_safe(top_unmet_name)} is the most frequently cited unmet need. "
        f"This represents both a market risk and an opportunity — "
        f"addressing it could differentiate the brand and improve patient outcomes.",
        "#10B981", "#0891B2"
    )
    kpis += "</div>"

    whats_next = _build_whats_next(
        "From headline numbers to platform intelligence",
        "Now that you see the overall landscape, the next section reveals "
        "where these conversations are happening and who is driving them.",
        [
            {"tab_id": "tab2", "num": "02", "title": "Platform & Stakeholder",
             "tease": f"Distribution across {n_platforms} platforms and reporter type breakdown"},
            {"tab_id": "tab3", "num": "03", "title": "Theme Intelligence",
             "tease": f"Deep dive into {n_themes} themes with patient verbatims"},
        ],
        "tab2", "Platform & Stakeholder"
    )

    return f"""
    <section class="tab-panel active" data-tab="tab1">
      <div class="page">
        {banner}
        {ctx}
        {kpis}
        {whats_next}
      </div>
    </section>"""


def _tab2_platform_stakeholder(stats: dict) -> str:
    """Tab 2: Platform & Stakeholder distribution."""
    valid = stats["valid"]
    plat_items = _top_n(stats["platforms"], 10)
    reporter_items = _top_n(stats["reporter_types"], 10)
    n_platforms = len(stats["platforms"])
    n_reporters = len(stats["reporter_types"])

    top_plat = plat_items[0] if plat_items else ("N/A", 0)
    top_reporter = reporter_items[0] if reporter_items else ("N/A", 0)

    banner = _build_section_banner(
        "tab2", "02", "Platform & Stakeholder Overview",
        f"Distribution across {n_platforms} platforms and {n_reporters} stakeholder types.",
        "b-brand1",
        [f"{n_platforms} Platforms", f"{n_reporters} Reporter Types",
         f"Top: {_safe(top_plat[0])} ({_pct(top_plat[1], valid)})"]
    )

    ctx = _build_context_setter(
        "&#128225;",
        f"{_safe(top_plat[0])} dominates platform share at {_pct(top_plat[1], valid)} of all posts.",
        f"Across {n_platforms} platforms, conversations cluster on {_safe(top_plat[0])}, "
        f"while {_safe(top_reporter[0])} is the most common reporter type "
        f"({_pct(top_reporter[1], valid)}). "
        f"This platform concentration shapes how intelligence should be activated "
        f"and which channels deserve investment.",
        "neutral"
    )

    # Platform distribution bars
    plat_bars = f"""
    <div class="card reveal d1">
      <div class="card-title">Platform Distribution (n={valid})
        <button class="insight-btn" onclick="openModal('platform-insight')">&#10022; Insights</button>
      </div>
      <div class="card-sub">Posts by source platform — bars animate on view</div>
      {_build_bar_rows(plat_items, valid, "var(--brand-1)")}
    </div>"""

    # Reporter type bars
    reporter_bars = f"""
    <div class="card reveal d2">
      <div class="card-title">Stakeholder Breakdown (n={valid})</div>
      <div class="card-sub">Reporter type distribution across coded posts</div>
      {_build_bar_rows(reporter_items, valid, "var(--brand-2)")}
    </div>"""

    whats_next = _build_whats_next(
        "From where conversations happen to what they say",
        "Platform distribution tells you where to listen. "
        "The next section reveals the dominant themes — the actual content of patient conversations.",
        [
            {"tab_id": "tab3", "num": "03", "title": "Theme Intelligence",
             "tease": f"Top themes across {valid} coded posts with patient verbatims"},
            {"tab_id": "tab4", "num": "04", "title": "Patient Journey",
             "tease": "Disease stage distribution with friction points per stage"},
        ],
        "tab3", "Theme Intelligence"
    )

    return f"""
    <section class="tab-panel" data-tab="tab2">
      <div class="page">
        {banner}
        {ctx}
        <div class="grid-2">
          {plat_bars}
          {reporter_bars}
        </div>
        {whats_next}
      </div>
    </section>"""


def _tab3_theme_intelligence(stats: dict, verbatims: list[dict]) -> str:
    """Tab 3: Theme Intelligence — theme distribution + patient quotes."""
    valid = stats["valid"]
    theme_items = _top_n(stats["themes"], 12, min_count=2)
    n_themes = len(stats["themes"])
    top_theme = theme_items[0] if theme_items else ("N/A", 0)

    banner = _build_section_banner(
        "tab3", "03", "Theme Intelligence",
        f"{n_themes} distinct themes identified — {_safe(top_theme[0])} leads at {_pct(top_theme[1], valid)}.",
        "b-brand2",
        [f"{n_themes} Themes", f"Top: {_safe(top_theme[0])}"]
    )

    ctx = _build_context_setter(
        "&#127991;",
        f"{_safe(top_theme[0])} accounts for {_pct(top_theme[1], valid)} of all coded posts.",
        f"Across {n_themes} themes, the narrative is concentrated. "
        f"The top theme alone captures {top_theme[1]} posts out of {valid}, "
        f"signalling a dominant conversation arc that should shape brand messaging, "
        f"medical education, and content strategy.",
        "neutral"
    )

    theme_bars = f"""
    <div class="card reveal d1">
      <div class="card-title">Theme Distribution
        <button class="insight-btn" onclick="openModal('theme-insight')">&#10022; Insights</button>
      </div>
      <div class="card-sub">Top themes by frequency — min. 2 posts to qualify</div>
      {_build_bar_rows(theme_items, valid, "var(--brand-2)")}
    </div>"""

    quotes = f"""
    <div class="card reveal d2">
      <div class="card-title">Real Patient Voices</div>
      <div class="card-sub">Direct verbatims from coded posts</div>
      {_build_quote_cards(verbatims, 5)}
    </div>"""

    whats_next = _build_whats_next(
        "From what patients discuss to where they are on their journey",
        "Themes reveal what matters — but context depends on where patients are "
        "in their disease journey. The next section maps conversations to disease stages.",
        [
            {"tab_id": "tab4", "num": "04", "title": "Patient Journey",
             "tease": f"Disease stage mapping with friction points per stage"},
            {"tab_id": "tab5", "num": "05", "title": "Unmet Needs",
             "tease": "What patients need but are not getting from current care"},
        ],
        "tab4", "Patient Journey"
    )

    return f"""
    <section class="tab-panel" data-tab="tab3">
      <div class="page">
        {banner}
        {ctx}
        <div class="grid-2">
          {theme_bars}
          {quotes}
        </div>
        {whats_next}
      </div>
    </section>"""


def _tab4_patient_journey(stats: dict, tagged_data: list[dict]) -> str:
    """Tab 4: Patient Journey — disease stage grid with friction points."""
    valid = stats["valid"]
    stage_items = _top_n(stats["stages"], 8)
    n_stages = len(stats["stages"])

    if not stage_items:
        top_stage_name = "N/A"
        top_stage_count = 0
    else:
        top_stage_name = stage_items[0][0]
        top_stage_count = stage_items[0][1]

    # Collect friction points per stage
    stage_frictions: dict[str, Counter] = {}
    for row in tagged_data:
        if row.get("error"):
            continue
        stage = row.get("stage", "")
        concern = row.get("concern", "")
        if stage and concern:
            stage_frictions.setdefault(stage, Counter())[concern] += 1

    banner = _build_section_banner(
        "tab4", "04", "Patient Journey",
        f"{n_stages} disease stages mapped with friction points per stage.",
        "b-brand3",
        [f"{n_stages} Stages", f"Top: {_safe(top_stage_name)} ({_pct(top_stage_count, valid)})"]
    )

    ctx = _build_context_setter(
        "&#128506;",
        f"The {_safe(top_stage_name)} stage dominates at {_pct(top_stage_count, valid)} of posts.",
        f"Patient conversations cluster around {n_stages} disease stages, "
        f"with {_safe(top_stage_name)} generating the most discussion. "
        f"Each stage has distinct friction points that reveal where patients struggle most "
        f"and where intervention can make the biggest impact.",
        "neutral" if stage_items else "warning"
    )

    # Journey grid
    cols = min(len(stage_items), 5) if stage_items else 1
    stages_html = ""
    for label, count in stage_items[:cols]:
        pct = _pct(count, valid)
        frictions = stage_frictions.get(label, Counter()).most_common(4)
        friction_items = "".join(f"<li>{_safe(f)}</li>" for f, _ in frictions)
        stages_html += (
            f'<div class="journey-stage reveal">'
            f'<div class="stage-label">{_safe(label)}</div>'
            f'<div class="stage-n" data-count="{count}">0</div>'
            f'<div class="stage-pct">{pct} of coded posts</div>'
            f'<ul class="stage-frictions">{friction_items}</ul>'
            f'</div>'
        )

    grid_cols = f"repeat({cols},1fr)" if cols > 0 else "1fr"

    journey_card = f"""
    <div class="card reveal" style="padding:0;overflow:hidden;">
      <div class="journey-wrap" style="grid-template-columns:{grid_cols};">
        {stages_html if stages_html else '<div style="padding:24px;color:var(--ink3);">No stage data available.</div>'}
      </div>
    </div>"""

    whats_next = _build_whats_next(
        "From journey stages to unmet clinical needs",
        "Understanding where patients are on their journey sets the stage. "
        "The next section reveals what they need but are not getting — the gaps that represent opportunity.",
        [
            {"tab_id": "tab5", "num": "05", "title": "Unmet Needs",
             "tease": "Distribution of unmet needs with patient voice quotes"},
            {"tab_id": "tab6", "num": "06", "title": "Concerns & QoL",
             "tease": "Patient concerns and quality of life impact analysis"},
        ],
        "tab5", "Unmet Needs"
    )

    return f"""
    <section class="tab-panel" data-tab="tab4">
      <div class="page">
        {banner}
        {ctx}
        {journey_card}
        {whats_next}
      </div>
    </section>"""


def _tab5_unmet_needs(stats: dict, verbatims: list[dict]) -> str:
    """Tab 5: Unmet Needs — need distribution + patient voice."""
    valid = stats["valid"]
    need_items = _top_n(stats["unmet_needs"], 10, min_count=2)
    n_needs = len(stats["unmet_needs"])
    top_need = need_items[0] if need_items else ("N/A", 0)

    banner = _build_section_banner(
        "tab5", "05", "Unmet Needs",
        f"{n_needs} distinct unmet needs identified from patient conversations.",
        "b-green",
        [f"{n_needs} Needs", f"Top: {_safe(top_need[0])}"]
    )

    ctx = _build_context_setter(
        "&#128138;",
        f"{_safe(top_need[0])} is the most cited unmet need at {_pct(top_need[1], valid)}.",
        f"Across {n_needs} distinct unmet needs, patients consistently express gaps in their care. "
        f"The leading need — {_safe(top_need[0])} — represents both a market risk "
        f"and a differentiation opportunity for brands that can address it "
        f"through product positioning, patient support programs, or clinical evidence.",
        "warning"
    )

    need_bars = f"""
    <div class="card reveal d1">
      <div class="card-title">Unmet Needs Distribution
        <button class="insight-btn" onclick="openModal('unmet-insight')">&#10022; Insights</button>
      </div>
      <div class="card-sub">Frequency of identified unmet needs — min. 2 posts to qualify</div>
      {_build_bar_rows(need_items, valid, "var(--pos)")}
    </div>"""

    quotes = f"""
    <div class="card reveal d2">
      <div class="card-title">Patient Voices on Unmet Needs</div>
      <div class="card-sub">Verbatims expressing unmet care needs</div>
      {_build_quote_cards(verbatims, 5)}
    </div>"""

    whats_next = _build_whats_next(
        "From unmet needs to risk signals and quality of life",
        "Unmet needs define the opportunity space. The next section reveals "
        "what patients fear and how their quality of life is impacted — "
        "the emotional and functional dimensions of the patient experience.",
        [
            {"tab_id": "tab6", "num": "06", "title": "Concerns & QoL",
             "tease": "Patient concerns, risk signals, and quality of life dimensions"},
            {"tab_id": "tab7", "num": "07", "title": "Strategic Implications",
             "tease": "Data-driven recommendations for brand and medical strategy"},
        ],
        "tab6", "Concerns & QoL"
    )

    return f"""
    <section class="tab-panel" data-tab="tab5">
      <div class="page">
        {banner}
        {ctx}
        <div class="grid-2">
          {need_bars}
          {quotes}
        </div>
        {whats_next}
      </div>
    </section>"""


def _tab6_concerns_qol(stats: dict, concern_verbatims: list[dict],
                       tagged_data: list[dict]) -> str:
    """Tab 6: Concerns & QoL — concern bars + QoL breakdown."""
    valid = stats["valid"]
    concern_items = _top_n(stats["concerns"], 10, min_count=2)
    qol_items = _top_n(stats["qol_impacts"], 10)
    n_concerns = len(stats["concerns"])
    n_qol = len(stats["qol_impacts"])
    top_concern = concern_items[0] if concern_items else ("N/A", 0)
    top_qol = qol_items[0] if qol_items else ("N/A", 0)

    banner = _build_section_banner(
        "tab6", "06", "Concerns & Quality of Life",
        f"{n_concerns} concerns and {n_qol} QoL dimensions impacting patient experience.",
        "b-red",
        [f"{n_concerns} Concerns", f"{n_qol} QoL Dimensions",
         f"Top: {_safe(top_concern[0])}"]
    )

    ctx = _build_context_setter(
        "&#9888;",
        f"Patient concern about {_safe(top_concern[0])} leads at {_pct(top_concern[1], valid)} of posts.",
        f"Concerns represent the emotional and practical barriers patients face. "
        f"When combined with quality of life impact data — {_safe(top_qol[0])} "
        f"leads at {_pct(top_qol[1], valid)} — a clear picture emerges of "
        f"where patients need the most support and where brand communications "
        f"should focus to build trust.",
        "risk"
    )

    concern_bars = f"""
    <div class="card reveal d1">
      <div class="card-title">Concern Distribution
        <button class="insight-btn" onclick="openModal('concern-insight')">&#10022; Insights</button>
      </div>
      <div class="card-sub">Patient concerns — min. 2 posts to qualify</div>
      {_build_bar_rows(concern_items, valid, "var(--neg)")}
    </div>"""

    qol_bars = f"""
    <div class="card reveal d2">
      <div class="card-title">QoL Impact Breakdown</div>
      <div class="card-sub">Quality of life dimensions impacted</div>
      {_build_bar_rows(qol_items, valid, "#0891B2")}
    </div>"""

    quotes_card = f"""
    <div class="card reveal d3">
      <div class="card-title">Patient Voices on Concerns</div>
      <div class="card-sub">Verbatims expressing patient concerns</div>
      {_build_quote_cards(concern_verbatims, 4)}
    </div>"""

    whats_next = _build_whats_next(
        "From patient pain points to strategic action",
        "Concerns and QoL data reveal the stakes. The final section "
        "translates all intelligence into prioritised strategic recommendations "
        "for brand, medical, and commercial teams.",
        [
            {"tab_id": "tab7", "num": "07", "title": "Strategic Implications",
             "tease": "Numbered strategy cards with evidence-based recommendations"},
            {"tab_id": "tab1", "num": "01", "title": "Executive Snapshot",
             "tease": "Return to the headline view for a refreshed perspective"},
        ],
        "tab7", "Strategic Implications"
    )

    return f"""
    <section class="tab-panel" data-tab="tab6">
      <div class="page">
        {banner}
        {ctx}
        <div class="grid-2">
          {concern_bars}
          {qol_bars}
        </div>
        {quotes_card}
        {whats_next}
      </div>
    </section>"""


def _tab7_strategic_implications(stats: dict) -> str:
    """Tab 7: Strategic Implications — numbered strategy cards."""
    valid = stats["valid"]
    top_themes = _top_n(stats["themes"], 3)
    top_concerns = _top_n(stats["concerns"], 3)
    top_unmet = _top_n(stats["unmet_needs"], 3)
    top_qol = _top_n(stats["qol_impacts"], 2)

    implications: list[dict] = []
    num = 1

    if top_themes:
        t_name, t_count = top_themes[0]
        implications.append({
            "num": num, "title": f"Address {t_name} as Priority Theme",
            "text": (f"{t_name} accounts for {_pct(t_count, valid)} of all coded posts. "
                     f"Develop targeted messaging and support programs around this "
                     f"dominant narrative to shape the conversation proactively."),
            "evidence": f"n={t_count} posts ({_pct(t_count, valid)})",
        })
        num += 1

    if top_concerns:
        c_name, c_count = top_concerns[0]
        implications.append({
            "num": num, "title": f"Mitigate {c_name} Concerns",
            "text": (f"Patient concern about {c_name} is the most frequently expressed "
                     f"({_pct(c_count, valid)}). Develop educational materials, "
                     f"HCP discussion guides, and proactive risk communications "
                     f"to address this head-on."),
            "evidence": f"n={c_count} posts ({_pct(c_count, valid)})",
        })
        num += 1

    if top_unmet:
        u_name, u_count = top_unmet[0]
        implications.append({
            "num": num, "title": f"Close the {u_name} Gap",
            "text": (f"{u_name} is the #1 unmet need ({_pct(u_count, valid)}). "
                     f"Evaluate R&D pipeline, partnership opportunities, and patient "
                     f"support programs to address this unmet need and differentiate."),
            "evidence": f"n={u_count} posts ({_pct(u_count, valid)})",
        })
        num += 1

    if top_qol:
        q_name, q_count = top_qol[0]
        implications.append({
            "num": num, "title": f"Prioritize {q_name} QoL Support",
            "text": (f"{q_name} quality of life impact dominates patient narratives. "
                     f"Integrate QoL endpoints into clinical programs, "
                     f"patient support services, and brand value propositions."),
            "evidence": f"n={q_count} posts ({_pct(q_count, valid)})",
        })
        num += 1

    if len(stats["platforms"]) > 1:
        plat_items = _top_n(stats["platforms"], 2)
        p2_name = plat_items[1][0] if len(plat_items) > 1 else "other platforms"
        implications.append({
            "num": num, "title": "Optimize Platform-Specific Engagement",
            "text": (f"Conversations span {len(stats['platforms'])} platforms. "
                     f"Tailor engagement: {plat_items[0][0]} for reach, "
                     f"{p2_name} for depth. "
                     f"Platform-specific strategies will maximize impact."),
            "evidence": f"{len(stats['platforms'])} platforms identified",
        })
        num += 1

    if len(stats["reporter_types"]) > 1:
        reps = _top_n(stats["reporter_types"], 3)
        rep_text = ", ".join(f"{r} ({_pct(c, valid)})" for r, c in reps)
        implications.append({
            "num": num, "title": "Segment by Stakeholder Voice",
            "text": (f"Reporter mix: {rep_text}. Design differentiated communications "
                     f"for each stakeholder archetype to maximize relevance and trust."),
            "evidence": f"{len(stats['reporter_types'])} reporter types",
        })

    n_implications = len(implications)
    banner = _build_section_banner(
        "tab7", "07", "Strategic Implications",
        f"{n_implications} data-driven recommendations for brand and medical strategy.",
        "b-gold",
        [f"{n_implications} Recommendations", "Evidence-Based"]
    )

    ctx = _build_context_setter(
        "&#127919;",
        f"{n_implications} strategic implications emerge from the intelligence.",
        "Every recommendation below is grounded in the data presented across "
        "the preceding sections. These are not generic suggestions — they are "
        "prioritised actions tied to specific signals in the patient conversation landscape. "
        "Each card includes the evidence base for executive decision-making.",
        "positive"
    )

    cards_html = ""
    for imp in implications:
        cards_html += f"""
        <div class="strat-card reveal">
          <div class="strat-num">{imp['num']}</div>
          <div>
            <div class="strat-title">{_safe(imp['title'])}</div>
            <div class="strat-text">{_safe(imp['text'])}</div>
            <div class="strat-evidence">{_safe(imp['evidence'])}</div>
          </div>
        </div>"""

    whats_next = _build_whats_next(
        "Intelligence cycle complete — return to the executive view",
        "You have reviewed all sections of this intelligence report. "
        "Return to the Executive Snapshot for a refreshed perspective, "
        "or revisit any section using the tab navigation above.",
        [
            {"tab_id": "tab1", "num": "01", "title": "Executive Snapshot",
             "tease": "Headline KPIs and the strategic compass for this report"},
            {"tab_id": "tab3", "num": "03", "title": "Theme Intelligence",
             "tease": "Revisit dominant themes and patient verbatims"},
        ],
        "tab1", "Executive Snapshot",
        is_last=True
    )

    return f"""
    <section class="tab-panel" data-tab="tab7">
      <div class="page">
        {banner}
        {ctx}
        <div class="strat-grid">
          {cards_html}
        </div>
        {whats_next}
      </div>
    </section>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  MODALS DATA BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _build_modals_js(stats: dict) -> str:
    """Build the MODALS JavaScript object with data-driven insight panels."""
    valid = stats["valid"]
    plat_items = _top_n(stats["platforms"], 3)
    theme_items = _top_n(stats["themes"], 3, min_count=2)
    concern_items = _top_n(stats["concerns"], 3, min_count=2)
    need_items = _top_n(stats["unmet_needs"], 3, min_count=2)

    top_plat = plat_items[0] if plat_items else ("N/A", 0)
    top_theme = theme_items[0] if theme_items else ("N/A", 0)
    top_concern = concern_items[0] if concern_items else ("N/A", 0)
    top_need = need_items[0] if need_items else ("N/A", 0)

    # Escape for JS string context
    def _js(text: str) -> str:
        return text.replace("'", "\\'").replace('"', '\\"').replace("\n", " ")

    return f"""
const MODALS = {{
  'platform-insight': {{
    tag: 'Section 02 \\u00B7 Platform Intelligence',
    title: 'Platform Distribution Analysis',
    body: `
      <div class="modal-stats">
        <div class="modal-stat"><div class="mv">{len(stats['platforms'])}</div><div class="ml">Platforms</div></div>
        <div class="modal-stat"><div class="mv">{_pct(top_plat[1], valid)}</div><div class="ml">Top Platform Share</div></div>
      </div>
      <p>Conversations span <strong>{len(stats['platforms'])} platforms</strong>. {_js(_safe(top_plat[0]))} accounts for {_pct(top_plat[1], valid)} of all posts, indicating concentrated engagement.</p>
      <p>This platform concentration suggests a primary channel for monitoring and engagement. Secondary platforms may serve niche communities with different conversation dynamics.</p>
      <p><strong>Action:</strong> Prioritize {_js(_safe(top_plat[0]))} for ongoing monitoring while developing platform-specific engagement strategies for secondary channels.</p>
    `
  }},
  'theme-insight': {{
    tag: 'Section 03 \\u00B7 Theme Intelligence',
    title: 'Theme Distribution Analysis',
    body: `
      <div class="modal-stats">
        <div class="modal-stat"><div class="mv">{len(stats['themes'])}</div><div class="ml">Themes</div></div>
        <div class="modal-stat"><div class="mv">{_pct(top_theme[1], valid)}</div><div class="ml">Top Theme Share</div></div>
      </div>
      <p>The top theme <strong>{_js(_safe(top_theme[0]))}</strong> dominates at {_pct(top_theme[1], valid)} of coded posts. This concentration suggests a primary narrative arc in patient conversations.</p>
      <p>Theme concentration this high signals an opportunity for brand messaging to align with patient concerns and establish thought leadership on the dominant topic.</p>
      <p><strong>Action:</strong> Develop content strategy and medical education materials centered on {_js(_safe(top_theme[0]))} to own the conversation.</p>
    `
  }},
  'concern-insight': {{
    tag: 'Section 06 \\u00B7 Concerns Intelligence',
    title: 'Patient Concerns Analysis',
    body: `
      <div class="modal-stats">
        <div class="modal-stat"><div class="mv">{len(stats['concerns'])}</div><div class="ml">Concerns</div></div>
        <div class="modal-stat"><div class="mv">{_pct(top_concern[1], valid)}</div><div class="ml">Top Concern Share</div></div>
      </div>
      <p><strong>{_js(_safe(top_concern[0]))}</strong> is the most frequently expressed concern at {_pct(top_concern[1], valid)} of posts. This represents the primary risk signal in the intelligence landscape.</p>
      <p>When patients voice concerns at this frequency, it indicates a potential barrier to treatment adherence, brand perception, or market access.</p>
      <p><strong>Action:</strong> Deploy educational materials and HCP discussion guides specifically addressing {_js(_safe(top_concern[0]))} to mitigate perceived risk.</p>
    `
  }},
  'unmet-insight': {{
    tag: 'Section 05 \\u00B7 Unmet Needs Intelligence',
    title: 'Unmet Needs Analysis',
    body: `
      <div class="modal-stats">
        <div class="modal-stat"><div class="mv">{len(stats['unmet_needs'])}</div><div class="ml">Unmet Needs</div></div>
        <div class="modal-stat"><div class="mv">{_pct(top_need[1], valid)}</div><div class="ml">Top Need Share</div></div>
      </div>
      <p><strong>{_js(_safe(top_need[0]))}</strong> is the most cited unmet need at {_pct(top_need[1], valid)} of posts. This gap in current care represents the single largest opportunity for differentiation.</p>
      <p>Unmet needs at this level indicate systematic gaps that cannot be addressed by messaging alone — they require product, service, or access improvements.</p>
      <p><strong>Action:</strong> Evaluate R&amp;D pipeline, patient support programs, and partnership opportunities to close the {_js(_safe(top_need[0]))} gap.</p>
    `
  }}
}};"""


# ═══════════════════════════════════════════════════════════════════════════════
#  JAVASCRIPT — complete skeleton from spec section 7
# ═══════════════════════════════════════════════════════════════════════════════

def _build_js(stats: dict) -> str:
    """Full JavaScript: state, tabs, flip cards, counters, bars, reveal, modals, particles."""
    tab_ids = [t["id"] for t in _TAB_META]
    tab_ids_js = ", ".join(f"'{t}'" for t in tab_ids)

    # Particle init calls — one per tab
    particle_inits = ""
    for t in _TAB_META:
        particle_inits += f"makeParticles('{t['id']}Particles', {t['particle_colors']});\n"

    modals_js = _build_modals_js(stats)

    return f"""
// ── STATE ────────────────────────────────────────────
const TABS = [{tab_ids_js}];
const visited = new Set(TABS);

// ── PROGRESS (always 100% since all sections visible) ──
function updateProgress() {{
  document.getElementById('progFill').style.width = '100%';
}}
updateProgress();

// ── SCROLL TO SECTION (replaces tab switching) ──────────
function switchTab(name) {{
  const panel = document.querySelector('.tab-panel[data-tab="' + name + '"]');
  if (panel) {{
    panel.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}
  // Highlight active nav tab
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.tab === name));
}}
// Wire nav buttons to scroll
document.querySelectorAll('.tab').forEach(btn => {{
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
}});

// ── SCROLL SPY — highlight nav tab on scroll ────────────
window.addEventListener('scroll', () => {{
  let current = TABS[0];
  TABS.forEach(id => {{
    const el = document.querySelector('.tab-panel[data-tab="' + id + '"]');
    if (el && el.getBoundingClientRect().top <= 150) current = id;
  }});
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.tab === current));
}});

// ── FLIP CARDS ───────────────────────────────────────
document.querySelectorAll('[data-flip]').forEach(card => {{
  card.addEventListener('click', () => card.classList.toggle('flipped'));
}});

// ── COUNTER ──────────────────────────────────────────
function countUp(el, target, dur) {{
  dur = dur || 1600;
  let s = 0;
  const inc = target / (dur / 16);
  const t = setInterval(() => {{
    s += inc;
    if (s >= target) {{ el.textContent = target.toLocaleString(); clearInterval(t); }}
    else {{ el.textContent = Math.floor(s).toLocaleString(); }}
  }}, 16);
}}

// ── INIT BARS (called on every tab switch) ───────────
function initBars() {{
  // All sections visible — init bars everywhere
  document.querySelectorAll('[data-w]').forEach(b => {{ b.style.width = b.dataset.w; }});
  document.querySelectorAll('[data-h]').forEach(b => {{ b.style.height = b.dataset.h; }});
}}

// ── SCROLL REVEAL ─────────────────────────────────────
const revObs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      e.target.classList.add('vis');
      e.target.querySelectorAll('[data-w]').forEach(b => {{
        setTimeout(() => {{ b.style.width = b.dataset.w; }}, 200);
      }});
      e.target.querySelectorAll('[data-count]').forEach(el => {{
        if (el.textContent === '0') countUp(el, parseInt(el.dataset.count));
      }});
      revObs.unobserve(e.target);
    }}
  }});
}}, {{ threshold: 0.08 }});
document.querySelectorAll('.reveal').forEach(el => revObs.observe(el));

// ── MODAL ─────────────────────────────────────────────
{modals_js}

function openModal(id) {{
  const d = MODALS[id]; if (!d) return;
  document.getElementById('mTag').textContent = d.tag;
  document.getElementById('mTitle').textContent = d.title;
  document.getElementById('mBody').innerHTML = d.body;
  document.getElementById('modalBg').classList.add('open');
}}
function closeModal(e) {{
  if (e && e.target !== document.getElementById('modalBg')) return;
  document.getElementById('modalBg').classList.remove('open');
}}
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('modalBg').classList.remove('open');
}});

// ── PARTICLES ─────────────────────────────────────────
function makeParticles(id, colors) {{
  const el = document.getElementById(id); if (!el) return;
  for (let i = 0; i < 18; i++) {{
    const p = document.createElement('div');
    const sz = 6 + Math.random() * 18;
    p.style.cssText = 'position:absolute;width:'+sz+'px;height:'+sz+'px;border-radius:50%;'+
      'background:'+colors[Math.floor(Math.random() * colors.length)]+';opacity:0;'+
      'left:'+(Math.random()*100)+'%;top:'+(Math.random()*100)+'%;'+
      'animation:floatUp '+(3+Math.random()*5)+'s '+(Math.random()*4)+'s linear infinite;';
    el.appendChild(p);
  }}
}}

// ── HERO COUNTERS ─────────────────────────────────────
setTimeout(() => {{
  document.querySelectorAll('.hero [data-count]').forEach(el => {{
    countUp(el, parseInt(el.dataset.count));
  }});
}}, 800);

// ── PARTICLES INIT ────────────────────────────────────
{particle_inits}

// ── INIT FIRST TAB ────────────────────────────────────
setTimeout(initBars, 400);
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_pharma_html_report(tagged_data: list[dict], metadata: dict) -> str:
    """
    Generate a complete, standalone, storyboarded HTML intelligence report
    from tagged pharma social intelligence data.

    Parameters
    ----------
    tagged_data : list[dict]
        Rows of tagged/analyzed data (output of the LLM tagging pipeline).
    metadata : dict
        Session metadata with keys like ``filename``, ``report_type``,
        ``context`` (a dict with ``focus_brand``, ``dataset_type``, etc.).

    Returns
    -------
    str
        A complete HTML document string.
    """
    # ── Compute statistics ────────────────────────────────────────────────
    stats = _collect_stats(tagged_data)

    # ── Derive title / subtitle ───────────────────────────────────────────
    context = metadata.get("context", {})
    focus_brand = context.get("focus_brand", "")
    filename = metadata.get("filename", "Report")

    title_base = focus_brand if focus_brand else filename.rsplit(".", 1)[0]
    title = f"{title_base} Social Intelligence"

    subtitle = (
        f"{stats['valid']} coded posts across {len(stats['platforms'])} platforms. "
        f"Pharma TA interactive intelligence report."
    )
    if context.get("additional_context"):
        subtitle += f" {context['additional_context']}."

    page_title = f"{title_base} — Social Intelligence Report"

    # ── Top items for hero ────────────────────────────────────────────────
    top_theme = _top_n(stats["themes"], 1)
    top_concern = _top_n(stats["concerns"], 1)
    top_theme_name = top_theme[0][0] if top_theme else "N/A"
    top_concern_name = top_concern[0][0] if top_concern else "N/A"

    # ── Section-specific verbatim quotes ──────────────────────────────────
    top_theme_names = [t for t, _ in stats["themes"].most_common(5)]
    theme_verbatims = _pick_verbatims(
        tagged_data, ["theme_verbatim"], max_count=6,
        filter_field="theme", filter_values=top_theme_names
    )
    top_need_names = [t for t, _ in stats["unmet_needs"].most_common(5)]
    need_verbatims = _pick_verbatims(
        tagged_data, ["unmet_need_verbatim"], max_count=5,
        filter_field="unmet_need", filter_values=top_need_names
    )
    top_concern_names = [t for t, _ in stats["concerns"].most_common(5)]
    concern_verbatims = _pick_verbatims(
        tagged_data, ["concern_verbatim"], max_count=5,
        filter_field="concern", filter_values=top_concern_names
    )

    # ── Tab buttons HTML ──────────────────────────────────────────────────
    tab_buttons = ""
    for i, t in enumerate(_TAB_META):
        active = " active" if i == 0 else ""
        tab_buttons += (
            f'<button class="tab{active}" data-tab="{t["id"]}">'
            f'<span class="tdot"></span>{_safe(t["label"])}</button>\n'
        )

    # ── Hero KPI strip ────────────────────────────────────────────────────
    valid = stats["valid"]
    hero_kpis = f"""
    <div class="hero-stats">
      <div class="hstat"><div class="v" data-count="{valid}">0</div><div class="l">Total Posts</div></div>
      <div class="hstat"><div class="v" data-count="{len(stats['platforms'])}">0</div><div class="l">Platforms</div></div>
      <div class="hstat"><div class="v" data-count="{len(stats['themes'])}">0</div><div class="l">Themes</div></div>
      <div class="hstat"><div class="v">{_safe(top_theme_name)}</div><div class="l">Top Theme</div></div>
    </div>"""

    # ── Build all tab panels ──────────────────────────────────────────────
    tab_panels = (
        _tab1_executive_snapshot(stats)
        + _tab2_platform_stakeholder(stats)
        + _tab3_theme_intelligence(stats, theme_verbatims)
        + _tab4_patient_journey(stats, tagged_data)
        + _tab5_unmet_needs(stats, need_verbatims)
        + _tab6_concerns_qol(stats, concern_verbatims, tagged_data)
        + _tab7_strategic_implications(stats)
    )

    # ── Build JS ──────────────────────────────────────────────────────────
    js = _build_js(stats)

    # ── Assemble complete HTML ────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_safe(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body>

<!-- READING PROGRESS BAR -->
<div class="prog-track"><div class="prog-fill" id="progFill"></div></div>

<!-- STICKY NAV -->
<div class="nav-wrap">
  <div class="nav-inner">
    <div class="brand">
      <div class="brand-mark">IV</div>
      <div class="brand-text">
        <div class="brand-name">InfoVision</div>
        <div class="brand-sub">Intelligence Report</div>
      </div>
    </div>
    <div class="tab-bar">
      {tab_buttons}
    </div>
  </div>
</div>

<!-- CINEMATIC HERO -->
<div class="hero">
  <div class="hero-overlay"></div>
  <div class="hero-grid"></div>
  <div class="hero-inner">
    <div class="hero-top">
      <div class="hero-eyebrow"><span class="dot"></span>Live Intelligence &middot; Pharma Social Intelligence</div>
      <div class="hero-chips">
        <div class="hero-chip">{_safe(title_base)}</div>
        <div class="hero-chip">Social Intelligence Report</div>
      </div>
    </div>
    <div class="hero-center">
      <h1 class="hero-title">{_safe(title)}</h1>
      <p class="hero-sub">{_safe(subtitle)}</p>
      {hero_kpis}
    </div>
  </div>
</div>

<!-- TAB PANELS -->
{tab_panels}

<!-- MODAL OVERLAY -->
<div class="modal-bg" id="modalBg" onclick="closeModal(event)">
  <div class="modal-box" id="modalBox">
    <button class="modal-close" onclick="document.getElementById('modalBg').classList.remove('open')">&#10005;</button>
    <div class="modal-tag" id="mTag"></div>
    <h3 class="modal-title" id="mTitle"></h3>
    <div class="modal-body" id="mBody"></div>
  </div>
</div>

<script>
{js}
</script>

</body>
</html>"""

    return html
