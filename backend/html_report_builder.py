"""
HTML Report Builder — generates a standalone, magazine-quality HTML report
from tagged pharma social intelligence data.

Produces an HTML file matching the InfoVision HPP Social Intelligence
template design system (purple #5B2EFF / magenta #FF4D8D gradient palette,
Plus Jakarta Sans + Sora typography, card-based layout).
"""

from __future__ import annotations

import html as _html
from collections import Counter
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA HELPERS
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
#  STATISTICS COLLECTOR
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
#  CSS (copied from the template)
# ═══════════════════════════════════════════════════════════════════════════════

_CSS = r"""
:root{--purple:#5B2EFF;--magenta:#FF4D8D;--grad:linear-gradient(135deg,#5B2EFF 0%,#FF4D8D 100%);--grad-soft:linear-gradient(135deg,rgba(91,46,255,0.08) 0%,rgba(255,77,141,0.08) 100%);--panel:#F7F7FA;--text:#1A1A2E;--text-mid:#4A4A6A;--text-soft:#8888AA;--border:#EDEDF5;--shadow:0 2px 16px rgba(91,46,255,0.07);--shadow-hover:0 8px 32px rgba(91,46,255,0.18);--nav-w:240px;--radius:16px;--radius-sm:10px;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Plus Jakarta Sans',sans-serif;background:var(--panel);color:var(--text);min-height:100vh;display:flex;}

/* SIDEBAR */
.sidebar{width:var(--nav-w);min-height:100vh;background:#fff;border-right:1px solid var(--border);position:fixed;top:0;left:0;display:flex;flex-direction:column;z-index:100;box-shadow:2px 0 24px rgba(91,46,255,0.06);}
.logo{padding:24px 20px 20px;border-bottom:1px solid var(--border);}
.logo-mark{font-family:'Sora',sans-serif;font-size:15px;font-weight:800;background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.logo-sub{font-size:10px;color:var(--text-soft);letter-spacing:0.08em;text-transform:uppercase;margin-top:2px;}
.nav-section{padding:16px 12px 8px;}
.nav-label{font-size:9.5px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--text-soft);padding:0 8px 8px;}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:10px;cursor:pointer;transition:all 0.18s;font-size:13px;font-weight:500;color:var(--text-mid);margin-bottom:2px;text-decoration:none;}
.nav-item:hover{background:var(--grad-soft);color:var(--purple);}
.nav-item.active{background:var(--grad);color:#fff;box-shadow:0 4px 14px rgba(91,46,255,0.3);}
.nav-icon{font-size:15px;width:18px;text-align:center;}
.nav-badge{margin-left:auto;background:var(--grad);color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:20px;}
.nav-item.active .nav-badge{background:rgba(255,255,255,0.3);}
.sidebar-footer{margin-top:auto;padding:16px;border-top:1px solid var(--border);font-size:11px;color:var(--text-soft);line-height:1.5;}
.sidebar-footer strong{color:var(--text-mid);}

.main{margin-left:var(--nav-w);flex:1;min-height:100vh;}
.topbar{background:#fff;border-bottom:1px solid var(--border);padding:0 32px;height:64px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:90;}
.page-title{font-family:'Sora',sans-serif;font-size:16px;font-weight:700;color:var(--text);letter-spacing:-0.3px;}
.page-sub{font-size:11px;color:var(--text-soft);margin-top:1px;}
.topbar-right{display:flex;align-items:center;gap:12px;}
.pill-tag{font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;background:var(--grad-soft);color:var(--purple);border:1px solid rgba(91,46,255,0.15);}
.pill-tag.alert{background:rgba(255,77,141,0.08);color:var(--magenta);border-color:rgba(255,77,141,0.2);}

/* HERO BANNER */
.hero-banner{position:relative;height:480px;overflow:hidden;display:flex;}
.hero-img-wrap{position:absolute;inset:0;}
.hero-overlay{position:absolute;inset:0;background:linear-gradient(105deg,rgba(10,0,40,0.92) 0%,rgba(20,0,80,0.85) 35%,rgba(91,46,255,0.55) 65%,rgba(255,77,141,0.25) 100%);}
.hero-chips{position:absolute;top:32px;left:48px;display:flex;gap:10px;z-index:5;}
.hero-chip{background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.22);backdrop-filter:blur(8px);padding:5px 16px;border-radius:20px;font-size:11px;font-weight:600;color:#fff;letter-spacing:0.04em;}
.hero-content{position:absolute;bottom:0;left:0;right:0;padding:0 48px 52px;z-index:5;display:flex;align-items:flex-end;justify-content:space-between;}
.hero-left{max-width:560px;}
.hero-eyebrow{font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.55);margin-bottom:12px;display:flex;align-items:center;gap:12px;}
.hero-eyebrow::before{content:'';display:block;width:28px;height:2px;background:#FF4D8D;border-radius:2px;flex-shrink:0;}
.hero-title{font-family:'Sora',sans-serif;font-size:56px;font-weight:800;color:#fff;line-height:1.0;letter-spacing:-2.5px;margin-bottom:16px;}
.hero-title em{color:#FFB3D4;font-style:normal;}
.hero-desc{font-size:14px;color:rgba(255,255,255,0.72);line-height:1.7;max-width:480px;}
.hero-kpis{display:flex;gap:20px;flex-direction:column;align-items:flex-end;}
.hero-kpi{background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.18);backdrop-filter:blur(12px);border-radius:14px;padding:14px 22px;text-align:center;min-width:110px;}
.hero-kpi-n{font-family:'Sora',sans-serif;font-size:26px;font-weight:800;color:#fff;line-height:1;}
.hero-kpi-l{font-size:9px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:0.1em;font-weight:600;margin-top:4px;}
.hero-kpi-row{display:flex;gap:12px;}

/* SECTION HEROES */
.sec-hero{display:flex;min-height:190px;border-radius:var(--radius);overflow:hidden;margin-bottom:24px;box-shadow:var(--shadow);}
.sh-img{width:45%;position:relative;overflow:hidden;flex-shrink:0;}
.sh-body{flex:1;padding:30px 36px;display:flex;flex-direction:column;justify-content:center;}
.sh-body.c1{background:linear-gradient(135deg,#3d00c8,#5B2EFF);}
.sh-body.c2{background:linear-gradient(135deg,#5d002a,#c40060);}
.sh-body.c3{background:linear-gradient(135deg,#04002a,#1a006e);}
.sh-body.c4{background:linear-gradient(135deg,#1a0060,#5B2EFF);}
.sh-body.c5{background:linear-gradient(135deg,#002050,#0040c0);}
.sh-body.c6{background:linear-gradient(135deg,#3d0020,#a0003a);}
.sh-eyebrow{font-size:9.5px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:rgba(255,255,255,0.45);margin-bottom:10px;}
.sh-title{font-family:'Sora',sans-serif;font-size:26px;font-weight:800;color:#fff;line-height:1.15;margin-bottom:12px;}
.sh-title em{color:#FFD6E7;font-style:normal;}
.sh-desc{font-size:12.5px;color:rgba(255,255,255,0.72);line-height:1.65;}
.sh-stats{display:flex;gap:28px;margin-top:18px;}
.sn{font-family:'Sora',sans-serif;font-size:24px;font-weight:800;color:#fff;line-height:1;}
.sl{font-size:9px;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.08em;font-weight:600;margin-top:3px;}
.sec-hero.flip .sh-img{order:2;}
.sec-hero.flip .sh-body{order:1;}

/* REST OF STYLES */
.content{padding:0 0 60px;}
.sw{padding:0 32px;}
.kpi-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px;}
.kpi-card{background:#fff;border-radius:var(--radius);padding:22px 20px;box-shadow:var(--shadow);border:1px solid var(--border);transition:all 0.2s;position:relative;overflow:hidden;}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad);}
.kpi-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-hover);}
.kpi-n{font-family:'Sora',sans-serif;font-size:34px;font-weight:800;background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1;margin-bottom:5px;}
.kpi-label{font-size:11.5px;font-weight:600;color:var(--text-mid);}
.kpi-sub{font-size:10.5px;color:var(--text-soft);margin-top:3px;}
.kpi-icon{position:absolute;top:18px;right:18px;font-size:22px;opacity:0.1;}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:28px;}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-bottom:28px;}
.grid-5-3{display:grid;grid-template-columns:5fr 3fr;gap:18px;margin-bottom:28px;}
.card{background:#fff;border-radius:var(--radius);padding:24px;box-shadow:var(--shadow);border:1px solid var(--border);transition:all 0.2s;}
.card:hover{box-shadow:var(--shadow-hover);}
.card-title{font-size:13px;font-weight:700;color:var(--text);margin-bottom:4px;display:flex;align-items:center;justify-content:space-between;}
.card-sub{font-size:11px;color:var(--text-soft);margin-bottom:18px;}
.sec-head{margin-bottom:20px;padding-top:8px;}
.sec-title{font-family:'Sora',sans-serif;font-size:18px;font-weight:700;color:var(--text);}
.sec-title span{background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.sec-desc{font-size:12.5px;color:var(--text-soft);margin-top:4px;max-width:600px;line-height:1.55;}
.sec-divider{height:3px;width:48px;border-radius:4px;background:var(--grad);margin-top:10px;}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:9px;}
.bar-lbl{font-size:12px;color:var(--text-mid);min-width:130px;text-align:right;font-weight:500;}
.bar-lbl.wide{min-width:180px;}
.bar-track{flex:1;background:var(--panel);border-radius:4px;height:9px;overflow:hidden;}
.bar-fill{height:100%;border-radius:4px;background:var(--grad);transition:width 1.1s cubic-bezier(.4,0,.2,1);}
.bar-fill.soft{background:linear-gradient(90deg,rgba(91,46,255,0.45),rgba(255,77,141,0.45));}
.bar-val{font-size:11.5px;font-weight:700;color:var(--text);min-width:60px;}
.journey-wrap{display:grid;grid-template-columns:repeat(4,1fr);gap:0;}
.journey-stage{padding:20px 18px;position:relative;border-right:1px solid var(--border);}
.journey-stage:last-child{border-right:none;}
.journey-stage:hover{background:var(--grad-soft);}
.journey-stage::after{content:'\2192';position:absolute;right:-14px;top:50%;transform:translateY(-50%);color:var(--text-soft);font-size:16px;z-index:2;}
.journey-stage:last-child::after{display:none;}
.stage-label{font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px;}
.stage-n{font-family:'Sora',sans-serif;font-size:30px;font-weight:800;color:var(--text);line-height:1;margin-bottom:4px;}
.stage-pct{font-size:11px;color:var(--text-soft);margin-bottom:10px;}
.stage-frictions{list-style:none;}
.stage-frictions li{font-size:11.5px;color:var(--text-mid);padding:3px 0;display:flex;gap:6px;align-items:flex-start;}
.stage-frictions li::before{content:'\00B7';color:var(--magenta);font-size:16px;line-height:1.1;flex-shrink:0;}
.strat-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:28px;}
.strat-card{background:#fff;border-radius:var(--radius);padding:22px;box-shadow:var(--shadow);border:1px solid var(--border);display:flex;gap:16px;}
.strat-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-hover);}
.strat-num{width:36px;height:36px;border-radius:10px;background:var(--grad);display:flex;align-items:center;justify-content:center;font-family:'Sora',sans-serif;font-size:15px;font-weight:800;color:#fff;flex-shrink:0;}
.strat-title{font-size:13.5px;font-weight:700;color:var(--text);margin-bottom:5px;}
.strat-text{font-size:12px;color:var(--text-mid);line-height:1.6;}
.strat-evidence{margin-top:8px;font-size:11px;font-weight:600;color:var(--purple);background:var(--grad-soft);padding:4px 10px;border-radius:6px;display:inline-block;}
.quote-card{background:var(--grad);border-radius:var(--radius-sm);padding:16px 18px;color:#fff;margin-bottom:10px;}
.quote-card:hover{opacity:0.9;}
.quote-text{font-size:12.5px;font-style:italic;line-height:1.6;margin-bottom:8px;}
.quote-meta{font-size:10px;font-weight:700;opacity:0.75;letter-spacing:0.06em;text-transform:uppercase;}
.progress-bar-wrap{margin-bottom:6px;}
.progress-bar-label{display:flex;justify-content:space-between;font-size:11.5px;color:var(--text-mid);margin-bottom:4px;font-weight:500;}
.progress-track{background:var(--panel);border-radius:6px;height:8px;overflow:hidden;}
.progress-fill{height:100%;border-radius:6px;background:var(--grad);}
.unmet-item{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);gap:12px;}
.unmet-item:last-child{border-bottom:none;}
.unmet-name{font-size:12.5px;color:var(--text-mid);font-weight:500;flex:1;}
.unmet-bar-wrap{width:100px;background:var(--panel);border-radius:4px;height:7px;overflow:hidden;}
.unmet-bar-fill{height:100%;border-radius:4px;background:var(--grad);}
.unmet-n{font-size:12px;font-weight:700;color:var(--text);min-width:26px;text-align:right;}
.alert-box{padding:12px 14px;background:rgba(255,77,141,0.06);border-radius:10px;border-left:3px solid var(--magenta);font-size:11.5px;color:var(--text-mid);line-height:1.6;margin-top:14px;}
.alert-box strong{color:var(--magenta);}
.info-box{padding:10px 14px;background:var(--panel);border-radius:10px;font-size:11.5px;color:var(--text-mid);line-height:1.6;margin-top:14px;}
.info-box strong{color:var(--purple);}
.insight-btn{font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px;background:var(--grad-soft);color:var(--purple);border:1px solid rgba(91,46,255,0.15);cursor:pointer;transition:all 0.18s;white-space:nowrap;display:inline-flex;align-items:center;gap:4px;}
.insight-btn:hover{background:var(--grad);color:#fff;border-color:transparent;}
.section{padding-bottom:32px;}
.section-gap{padding:28px 0 32px;}

/* Modal */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:200;justify-content:center;align-items:center;backdrop-filter:blur(4px);}
.modal-overlay.active{display:flex;}
.modal{background:#fff;border-radius:var(--radius);max-width:600px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:0 24px 64px rgba(91,46,255,0.2);padding:32px;position:relative;animation:modalIn 0.3s ease-out;}
@keyframes modalIn{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}
.modal-close{position:absolute;top:16px;right:16px;width:32px;height:32px;border-radius:8px;border:none;background:var(--panel);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;color:var(--text-mid);transition:all 0.15s;}
.modal-close:hover{background:var(--grad);color:#fff;}
.modal-title{font-family:'Sora',sans-serif;font-size:18px;font-weight:700;margin-bottom:6px;}
.modal-sub{font-size:12px;color:var(--text-soft);margin-bottom:18px;}
.modal p{font-size:13px;color:var(--text-mid);line-height:1.7;margin-bottom:12px;}

@media (max-width:900px){
  .sidebar{display:none;}
  .main{margin-left:0;}
}

/* Print friendly */
@media print{
  body{background:#fff;}
  .topbar{position:relative;}
  .kpi-card::before{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  .hero-banner,.sec-hero,.quote-card,.strat-num,.bar-fill,.progress-fill,.unmet-bar-fill{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  HTML SECTION BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_hero(title: str, subtitle: str, stats: dict) -> str:
    valid = stats["valid"]
    n_platforms = len(stats["platforms"])

    # Top platform
    top_plat = _top_n(stats["platforms"], 1)
    top_plat_name = top_plat[0][0] if top_plat else "N/A"
    top_plat_pct = _pct(top_plat[0][1], valid) if top_plat else "0%"

    return f"""
  <div class="hero-banner">
    <div class="hero-img-wrap" style="background:linear-gradient(135deg,#1a0060 0%,#5B2EFF 40%,#FF4D8D 100%);"></div>
    <div class="hero-overlay"></div>
    <div class="hero-chips">
      <div class="hero-chip">Social Intelligence Report</div>
      <div class="hero-chip">{_safe(str(n_platforms))} Platforms</div>
    </div>
    <div class="hero-content">
      <div class="hero-left">
        <div class="hero-eyebrow">Pharma TA Intelligence</div>
        <h1 class="hero-title">{_safe(title)}</h1>
        <p class="hero-desc">{_safe(subtitle)}</p>
      </div>
      <div class="hero-kpis">
        <div class="hero-kpi-row">
          <div class="hero-kpi"><div class="hero-kpi-n">{valid}</div><div class="hero-kpi-l">Total Posts</div></div>
          <div class="hero-kpi"><div class="hero-kpi-n">{n_platforms}</div><div class="hero-kpi-l">Platforms</div></div>
        </div>
        <div class="hero-kpi-row">
          <div class="hero-kpi"><div class="hero-kpi-n">{len(stats['themes'])}</div><div class="hero-kpi-l">Themes</div></div>
          <div class="hero-kpi"><div class="hero-kpi-n">{top_plat_pct}</div><div class="hero-kpi-l">{_safe(top_plat_name)}</div></div>
        </div>
      </div>
    </div>
  </div>
"""


def _build_kpi_cards(stats: dict) -> str:
    valid = stats["valid"]
    top_plat = _top_n(stats["platforms"], 1)
    top_concern = _top_n(stats["concerns"], 1)
    top_unmet = _top_n(stats["unmet_needs"], 1)
    top_qol = _top_n(stats["qol_impacts"], 1)

    cards = [
        ("Total Coded Posts",
         str(valid),
         f"{len(stats['platforms'])} platforms",
         "&#128202;"),
        (f"{_safe(top_plat[0][0]) if top_plat else 'Top Platform'} Share",
         _pct(top_plat[0][1], valid) if top_plat else "0%",
         f"{top_plat[0][1]} of {valid} posts" if top_plat else "",
         "&#128038;"),
        (f"Concern: {_safe(top_concern[0][0]) if top_concern else 'N/A'}",
         _pct(top_concern[0][1], valid) if top_concern else "0%",
         f"{top_concern[0][1]} of {valid} posts" if top_concern else "",
         "&#9888;"),
        (f"Unmet Need: {_safe(top_unmet[0][0]) if top_unmet else 'N/A'}",
         _pct(top_unmet[0][1], valid) if top_unmet else "0%",
         f"{top_unmet[0][1]} of {valid} posts" if top_unmet else "",
         "&#128138;"),
        (f"QoL: {_safe(top_qol[0][0]) if top_qol else 'N/A'}",
         _pct(top_qol[0][1], valid) if top_qol else "0%",
         f"{top_qol[0][1]} of {valid} posts" if top_qol else "",
         "&#127973;"),
    ]

    html_parts = ['<div class="kpi-grid">']
    for label, number, sub, icon in cards:
        html_parts.append(f"""
        <div class="kpi-card">
          <div class="kpi-icon">{icon}</div>
          <div class="kpi-n">{_safe(number)}</div>
          <div class="kpi-label">{label}</div>
          <div class="kpi-sub">{_safe(sub)}</div>
        </div>""")
    html_parts.append("</div>")
    return "\n".join(html_parts)


def _build_bar_chart(items: list[tuple[str, int]], total: int,
                     wide: bool = False, soft: bool = False) -> str:
    """Build horizontal bar chart rows."""
    if not items:
        return '<div class="info-box">No data available for this section.</div>'
    max_val = items[0][1] if items else 1
    parts: list[str] = []
    for label, count in items:
        bar_w = max(1, int(count / max_val * 100)) if max_val else 0
        pct = _pct(count, total)
        lbl_cls = "bar-lbl wide" if wide else "bar-lbl"
        fill_cls = "bar-fill soft" if soft else "bar-fill"
        parts.append(
            f'<div class="bar-row">'
            f'<div class="{lbl_cls}">{_safe(label)}</div>'
            f'<div class="bar-track"><div class="{fill_cls}" style="width:{bar_w}%"></div></div>'
            f'<div class="bar-val">{count} &nbsp;{pct}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def _build_section_hero(eyebrow: str, title: str, desc: str,
                        color_class: str = "c1", flip: bool = False,
                        stat_pairs: list[tuple[str, str]] | None = None) -> str:
    """Section hero with gradient background (no images)."""
    flip_cls = " flip" if flip else ""
    gradient_bg = {
        "c1": "linear-gradient(135deg,#3d00c8 0%,#5B2EFF 50%,#7B4AFF 100%)",
        "c2": "linear-gradient(135deg,#5d002a 0%,#c40060 50%,#FF4D8D 100%)",
        "c3": "linear-gradient(135deg,#04002a 0%,#1a006e 50%,#3d00c8 100%)",
        "c4": "linear-gradient(135deg,#1a0060 0%,#5B2EFF 50%,#7B4AFF 100%)",
        "c5": "linear-gradient(135deg,#002050 0%,#0040c0 50%,#0060e0 100%)",
        "c6": "linear-gradient(135deg,#3d0020 0%,#a0003a 50%,#FF4D8D 100%)",
    }.get(color_class, "linear-gradient(135deg,#3d00c8,#5B2EFF)")

    stats_html = ""
    if stat_pairs:
        stat_items = "".join(
            f'<div><div class="sn">{_safe(v)}</div><div class="sl">{_safe(l)}</div></div>'
            for l, v in stat_pairs
        )
        stats_html = f'<div class="sh-stats">{stat_items}</div>'

    return f"""
    <div class="sec-hero{flip_cls}">
      <div class="sh-img" style="background:{gradient_bg};"></div>
      <div class="sh-body {color_class}">
        <div class="sh-eyebrow">{_safe(eyebrow)}</div>
        <div class="sh-title">{title}</div>
        <div class="sh-desc">{_safe(desc)}</div>
        {stats_html}
      </div>
    </div>"""


def _build_quote_cards(verbatims: list[dict], max_cards: int = 5) -> str:
    """Build styled verbatim quote cards."""
    gradients = [
        "linear-gradient(135deg,#5B2EFF,#FF4D8D)",
        "linear-gradient(135deg,#7B4AFF,#FF4D8D)",
        "linear-gradient(135deg,#FF4D8D,#FF8C4B)",
        "linear-gradient(135deg,#3d00c8,#5B2EFF)",
        "linear-gradient(135deg,#5d002a,#c40060)",
    ]
    parts: list[str] = []
    for i, v in enumerate(verbatims[:max_cards]):
        grad = gradients[i % len(gradients)]
        meta_parts = [_safe(v.get("reporter", ""))]
        if v.get("platform"):
            meta_parts.append(_safe(v["platform"]))
        if v.get("stage"):
            meta_parts.append(_safe(v["stage"]))
        meta = " &middot; ".join([p for p in meta_parts if p])
        parts.append(
            f'<div class="quote-card" style="background:{grad}">'
            f'<div class="quote-text">&ldquo;{_safe(v["text"])}&rdquo;</div>'
            f'<div class="quote-meta">{meta}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def _build_platform_section(stats: dict) -> str:
    valid = stats["valid"]
    plat_items = _top_n(stats["platforms"], 10)
    reporter_items = _top_n(stats["reporter_types"], 10)
    top_plat_count = plat_items[0][1] if plat_items else 0

    return f"""
    <div id="platforms" class="section">
      {_build_section_hero(
          "Section 01", "Platform &amp; <em>Stakeholder</em> Overview",
          f"Distribution across {len(stats['platforms'])} platforms and reporter type breakdown.",
          "c1", False,
          [("Platforms", str(len(stats["platforms"]))),
           ("Reporter Types", str(len(stats["reporter_types"])))]
      )}
      <div class="grid-2">
        <div class="card">
          <div class="card-title">Platform Distribution (n={valid})<button class="insight-btn" onclick="openModal('Platform Insights','AI-generated analysis','<p>Conversations span <strong>{len(stats['platforms'])} platforms</strong>. The dominant platform accounts for {_pct(top_plat_count, valid)} of all posts, suggesting concentrated engagement. Tailor platform-specific strategies for maximum reach.</p>')">✦ AI Insights</button></div>
          <div class="card-sub">Posts by source platform</div>
          {_build_bar_chart(plat_items, valid, soft=True)}
        </div>
        <div class="card">
          <div class="card-title">Stakeholder Breakdown (n={valid})</div>
          <div class="card-sub">Reporter type distribution</div>
          {_build_bar_chart(reporter_items, valid)}
        </div>
      </div>
    </div>"""


def _build_themes_section(stats: dict, verbatims: list[dict]) -> str:
    valid = stats["valid"]
    theme_items = _top_n(stats["themes"], 12, min_count=2)
    theme_verbatims = verbatims[:5]

    return f"""
    <div id="themes" class="section">
      {_build_section_hero(
          "Section 02", "Theme <em>Analysis</em>",
          f"Top themes identified across {valid} coded posts.",
          "c2", True,
          [("Themes", str(len(stats["themes"]))),
           ("Top Theme", _safe(theme_items[0][0]) if theme_items else "N/A")]
      )}
      <div class="grid-5-3">
        <div class="card">
          <div class="card-title">Theme Distribution<button class="insight-btn" onclick="openModal('Theme Insights','AI-generated analysis','<p>The top theme dominates with <strong>{_pct(theme_items[0][1] if theme_items else 0, valid)}</strong> of coded posts. This concentration suggests a primary narrative that should be addressed in brand strategy and medical communications.</p>')">✦ AI Insights</button></div>
          <div class="card-sub">Horizontal bar chart of top themes with counts and percentages</div>
          {_build_bar_chart(theme_items, valid, wide=True)}
        </div>
        <div class="card">
          <div class="card-title">Real Patient Voices</div>
          <div class="card-sub">Direct verbatims from coded posts</div>
          {_build_quote_cards(theme_verbatims)}
        </div>
      </div>
    </div>"""


def _build_journey_section(stats: dict, tagged_data: list[dict]) -> str:
    valid = stats["valid"]
    stage_items = _top_n(stats["stages"], 8)

    if not stage_items:
        return ""

    # Collect friction points per stage
    stage_frictions: dict[str, Counter] = {}
    for row in tagged_data:
        if row.get("error"):
            continue
        stage = row.get("stage", "")
        concern = row.get("concern", "")
        if stage and concern:
            stage_frictions.setdefault(stage, Counter())[concern] += 1

    # Build journey stages (max 4-5)
    cols = min(len(stage_items), 5)
    stages_html_parts: list[str] = []
    for label, count in stage_items[:cols]:
        pct = _pct(count, valid)
        frictions = stage_frictions.get(label, Counter()).most_common(4)
        friction_items = "".join(
            f"<li>{_safe(f)}</li>" for f, _ in frictions
        )
        stages_html_parts.append(
            f'<div class="journey-stage">'
            f'<div class="stage-label">{_safe(label)}</div>'
            f'<div class="stage-n">{count}</div>'
            f'<div class="stage-pct">{pct} of stage posts</div>'
            f'<ul class="stage-frictions">{friction_items}</ul>'
            f'</div>'
        )

    grid_cols = f"repeat({cols},1fr)"

    return f"""
    <div id="journey" class="section">
      {_build_section_hero(
          "Section 03", "Patient <em>Journey</em>",
          "Disease stage distribution with top friction points per stage.",
          "c3", False,
          [("Stages", str(len(stats["stages"]))),
           ("Top Stage", f"{stage_items[0][0]} ({_pct(stage_items[0][1], valid)})" if stage_items else "N/A")]
      )}
      <div class="card" style="padding:0;overflow:hidden;">
        <div class="journey-wrap" style="grid-template-columns:{grid_cols};">
          {"".join(stages_html_parts)}
        </div>
      </div>
    </div>"""


def _build_unmet_needs_section(stats: dict, verbatims: list[dict]) -> str:
    valid = stats["valid"]
    need_items = _top_n(stats["unmet_needs"], 10, min_count=2)
    need_verbatims = verbatims[:4]

    if not need_items:
        return ""

    return f"""
    <div id="unmet" class="section">
      {_build_section_hero(
          "Section 04", "Unmet <em>Needs</em>",
          f"{len(stats['unmet_needs'])} distinct unmet needs identified.",
          "c4", True,
          [("Unmet Needs", str(len(stats["unmet_needs"]))),
           ("Top Need", _safe(need_items[0][0]) if need_items else "N/A")]
      )}
      <div class="grid-5-3">
        <div class="card">
          <div class="card-title">Unmet Needs Distribution</div>
          <div class="card-sub">Frequency of identified unmet needs</div>
          {_build_bar_chart(need_items, valid, wide=True)}
        </div>
        <div class="card">
          <div class="card-title">Patient Voices on Unmet Needs</div>
          <div class="card-sub">Verbatims expressing unmet needs</div>
          {_build_quote_cards(need_verbatims, 4)}
        </div>
      </div>
    </div>"""


def _build_concerns_section(stats: dict, verbatims: list[dict]) -> str:
    valid = stats["valid"]
    concern_items = _top_n(stats["concerns"], 10, min_count=2)
    concern_verbatims = verbatims[:4]

    if not concern_items:
        return ""

    return f"""
    <div id="concerns" class="section">
      {_build_section_hero(
          "Section 05", "Patient <em>Concerns</em>",
          f"{len(stats['concerns'])} distinct concerns identified across {valid} posts.",
          "c5", False,
          [("Concerns", str(len(stats["concerns"]))),
           ("Top Concern", _safe(concern_items[0][0]) if concern_items else "N/A")]
      )}
      <div class="grid-5-3">
        <div class="card">
          <div class="card-title">Concern Distribution</div>
          <div class="card-sub">Frequency of patient concerns</div>
          {_build_bar_chart(concern_items, valid, wide=True, soft=True)}
        </div>
        <div class="card">
          <div class="card-title">Patient Voices on Concerns</div>
          <div class="card-sub">Verbatims expressing concerns</div>
          {_build_quote_cards(concern_verbatims, 4)}
        </div>
      </div>
    </div>"""


def _build_qol_section(stats: dict, tagged_data: list[dict]) -> str:
    valid = stats["valid"]
    qol_items = _top_n(stats["qol_impacts"], 10)

    if not qol_items:
        return ""

    # Collect sub-issues per QoL category
    qol_sub: dict[str, Counter] = {}
    for row in tagged_data:
        if row.get("error"):
            continue
        qol = row.get("qol_impact", "")
        theme = row.get("theme", "")
        if qol and theme:
            qol_sub.setdefault(qol, Counter())[theme] += 1

    # Build progress bars for QoL categories
    max_count = qol_items[0][1] if qol_items else 1
    progress_parts: list[str] = []
    for label, count in qol_items:
        pct_val = _pct_float(count, valid)
        bar_w = max(1, int(count / max_count * 100)) if max_count else 0
        sub_issues = qol_sub.get(label, Counter()).most_common(3)
        sub_text = ", ".join(f"{_safe(s)}" for s, _ in sub_issues)
        progress_parts.append(
            f'<div class="progress-bar-wrap">'
            f'<div class="progress-bar-label">'
            f'<span>{_safe(label)}</span>'
            f'<span>{count} ({pct_val}%)</span>'
            f'</div>'
            f'<div class="progress-track"><div class="progress-fill" style="width:{bar_w}%"></div></div>'
            f'</div>'
        )
        if sub_text:
            progress_parts.append(
                f'<div class="info-box" style="margin-top:4px;margin-bottom:12px;">'
                f'<strong>Sub-issues:</strong> {sub_text}</div>'
            )

    return f"""
    <div id="qol" class="section">
      {_build_section_hero(
          "Section 06", "Quality of <em>Life</em> Impact",
          "Breakdown by Physical, Emotional, Social, Occupational dimensions.",
          "c6", True,
          [("QoL Dimensions", str(len(stats["qol_impacts"]))),
           ("Top Impact", _safe(qol_items[0][0]) if qol_items else "N/A")]
      )}
      <div class="card">
        <div class="card-title">QoL Impact Distribution</div>
        <div class="card-sub">Impact across quality of life dimensions</div>
        {"".join(progress_parts)}
      </div>
    </div>"""


def _build_implications_section(stats: dict) -> str:
    """Generate strategic implications from the data."""
    implications: list[dict] = []

    # Generate implications based on actual data patterns
    top_themes = _top_n(stats["themes"], 3)
    top_concerns = _top_n(stats["concerns"], 3)
    top_unmet = _top_n(stats["unmet_needs"], 3)
    top_qol = _top_n(stats["qol_impacts"], 2)
    valid = stats["valid"]

    num = 1
    if top_themes:
        t_name, t_count = top_themes[0]
        implications.append({
            "num": num, "title": f"Address {t_name} as Priority Theme",
            "text": f"{t_name} accounts for {_pct(t_count, valid)} of all coded posts. "
                    f"Develop targeted messaging and support programs around this dominant narrative.",
            "evidence": f"n={t_count} posts ({_pct(t_count, valid)})",
        })
        num += 1

    if top_concerns:
        c_name, c_count = top_concerns[0]
        implications.append({
            "num": num, "title": f"Mitigate {c_name} Concerns",
            "text": f"Patient concern about {c_name} is the most frequently expressed "
                    f"({_pct(c_count, valid)}). Consider educational materials and HCP discussion guides.",
            "evidence": f"n={c_count} posts ({_pct(c_count, valid)})",
        })
        num += 1

    if top_unmet:
        u_name, u_count = top_unmet[0]
        implications.append({
            "num": num, "title": f"Close the {u_name} Gap",
            "text": f"{u_name} is the #1 unmet need ({_pct(u_count, valid)}). "
                    f"Evaluate R&D pipeline and partnerships to address this unmet need.",
            "evidence": f"n={u_count} posts ({_pct(u_count, valid)})",
        })
        num += 1

    if top_qol:
        q_name, q_count = top_qol[0]
        implications.append({
            "num": num, "title": f"Prioritize {q_name} QoL Support",
            "text": f"{q_name} quality of life impact dominates patient narratives. "
                    f"Integrate QoL endpoints into clinical programs and patient support.",
            "evidence": f"n={q_count} posts ({_pct(q_count, valid)})",
        })
        num += 1

    if len(stats["platforms"]) > 1:
        plat_items = _top_n(stats["platforms"], 2)
        implications.append({
            "num": num, "title": "Optimize Platform-Specific Engagement",
            "text": f"Conversations span {len(stats['platforms'])} platforms. "
                    f"Tailor engagement strategy: {plat_items[0][0]} for reach, "
                    f"{plat_items[1][0] if len(plat_items) > 1 else 'other platforms'} for depth.",
            "evidence": f"{len(stats['platforms'])} platforms identified",
        })
        num += 1

    if len(stats["reporter_types"]) > 1:
        reps = _top_n(stats["reporter_types"], 3)
        rep_text = ", ".join(f"{r} ({_pct(c, valid)})" for r, c in reps)
        implications.append({
            "num": num, "title": "Segment by Stakeholder Voice",
            "text": f"Reporter mix: {rep_text}. Design differentiated communications "
                    f"for each stakeholder archetype.",
            "evidence": f"{len(stats['reporter_types'])} reporter types",
        })
        num += 1

    # Build the HTML
    cards_html = ""
    for imp in implications:
        cards_html += f"""
        <div class="strat-card">
          <div class="strat-num">{imp['num']}</div>
          <div>
            <div class="strat-title">{_safe(imp['title'])}</div>
            <div class="strat-text">{_safe(imp['text'])}</div>
            <div class="strat-evidence">{_safe(imp['evidence'])}</div>
          </div>
        </div>"""

    return f"""
    <div id="strategy" class="section">
      {_build_section_hero(
          "Section 07", "Strategic <em>Implications</em>",
          "Data-driven recommendations for brand and medical strategy.",
          "c3", False,
          [("Implications", str(len(implications)))]
      )}
      <div class="strat-grid">
        {cards_html}
      </div>
    </div>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_pharma_html_report(tagged_data: list[dict], metadata: dict) -> str:
    """
    Generate a complete, standalone HTML report from tagged pharma social
    intelligence data.

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

    # Build a human-readable title
    title_base = focus_brand if focus_brand else filename.rsplit(".", 1)[0]
    top_theme = _top_n(stats["themes"], 1)
    title = f"{title_base} Social Intelligence"

    subtitle = (
        f"{stats['valid']} coded posts across {len(stats['platforms'])} platforms. "
        f"Pharma TA intelligence report."
    )
    if context.get("additional_context"):
        subtitle += f" {context['additional_context']}."

    page_title = f"{title_base} — Social Intelligence Report"

    # ── Select SECTION-SPECIFIC verbatim quotes (no repeats across sections) ──
    top_themes = [t for t, _ in stats["themes"].most_common(5)]
    theme_verbatims = _pick_verbatims(tagged_data, ["theme_verbatim"], max_count=6,
                                       filter_field="theme", filter_values=top_themes)
    top_needs = [t for t, _ in stats["unmet_needs"].most_common(5)]
    need_verbatims = _pick_verbatims(tagged_data, ["unmet_need_verbatim"], max_count=5,
                                      filter_field="unmet_need", filter_values=top_needs)
    top_concerns = [t for t, _ in stats["concerns"].most_common(5)]
    concern_verbatims = _pick_verbatims(tagged_data, ["concern_verbatim"], max_count=5,
                                         filter_field="concern", filter_values=top_concerns)
    qol_verbatims = _pick_verbatims(tagged_data, ["qol_verbatim"], max_count=4)

    # ── Assemble the full HTML ────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_safe(page_title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Sora:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body>

<!-- SIDEBAR NAV -->
<aside class="sidebar">
  <div class="logo">
    <div class="logo-mark">InfoVision</div>
    <div class="logo-sub">Consumer Intelligence</div>
  </div>
  <div class="nav-section">
    <div class="nav-label">Report Sections</div>
    <a href="#overview" class="nav-item active" onclick="setActive(this)"><span class="nav-icon">📊</span>Overview</a>
    <a href="#platforms" class="nav-item" onclick="setActive(this)"><span class="nav-icon">📡</span>Platforms<span class="nav-badge">{len(stats['platforms'])}</span></a>
    <a href="#themes" class="nav-item" onclick="setActive(this)"><span class="nav-icon">🏷️</span>Themes<span class="nav-badge">{len(stats['themes'])}</span></a>
    <a href="#journey" class="nav-item" onclick="setActive(this)"><span class="nav-icon">🗺️</span>Patient Journey</a>
    <a href="#unmet" class="nav-item" onclick="setActive(this)"><span class="nav-icon">💊</span>Unmet Needs<span class="nav-badge">{len(stats['unmet_needs'])}</span></a>
    <a href="#concerns" class="nav-item" onclick="setActive(this)"><span class="nav-icon">⚠️</span>Concerns<span class="nav-badge">{len(stats['concerns'])}</span></a>
    <a href="#qol" class="nav-item" onclick="setActive(this)"><span class="nav-icon">❤️</span>Quality of Life</a>
    <a href="#strategy" class="nav-item" onclick="setActive(this)"><span class="nav-icon">🎯</span>Implications</a>
  </div>
  <div class="sidebar-footer">
    <strong>AI-Generated Report</strong><br>
    {stats['valid']} posts · {len(stats['platforms'])} platforms<br>
    Pharma Social Intelligence
  </div>
</aside>

<main class="main">
  <div class="topbar">
    <div>
      <div class="page-title">{_safe(page_title)}</div>
      <div class="page-sub">{_safe(subtitle)}</div>
    </div>
    <div class="topbar-right">
      <span class="pill-tag">Social Intelligence</span>
      <span class="pill-tag alert">Pharma TA</span>
    </div>
  </div>

  {_build_hero(title, subtitle, stats)}

  <div class="content"><div class="sw">

    <!-- KPIs -->
    <div id="overview" class="section-gap">
      <div class="sec-head">
        <div class="sec-title">Executive <span>Overview</span></div>
        <div class="sec-desc">{stats['valid']} posts coded across {len(stats['themes'])} themes. Generated from tagged analysis data.</div>
        <div class="sec-divider"></div>
      </div>
      {_build_kpi_cards(stats)}
    </div>

    {_build_platform_section(stats)}

    {_build_themes_section(stats, theme_verbatims)}

    {_build_journey_section(stats, tagged_data)}

    {_build_unmet_needs_section(stats, need_verbatims)}

    {_build_concerns_section(stats, concern_verbatims)}

    {_build_qol_section(stats, tagged_data)}

    {_build_implications_section(stats)}

  </div></div>
</main>

<!-- MODAL CONTAINER -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <div class="modal-title" id="modalTitle"></div>
    <div class="modal-sub" id="modalSub"></div>
    <div id="modalBody"></div>
  </div>
</div>

<script>
// Smooth scrolling for sidebar nav
document.querySelectorAll('.nav-item').forEach(link => {{
  link.addEventListener('click', function(e) {{
    const href = this.getAttribute('href');
    if (href && href.startsWith('#')) {{
      e.preventDefault();
      const target = document.getElementById(href.slice(1));
      if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}
  }});
}});

function setActive(el) {{
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  el.classList.add('active');
}}

// Highlight active nav on scroll
const sections = document.querySelectorAll('.section, .section-gap');
const navItems = document.querySelectorAll('.sidebar .nav-item');
window.addEventListener('scroll', () => {{
  let current = '';
  sections.forEach(sec => {{
    if (sec.offsetTop - 200 <= window.scrollY) current = sec.id;
  }});
  navItems.forEach(item => {{
    item.classList.remove('active');
    if (item.getAttribute('href') === '#' + current) item.classList.add('active');
  }});
}});

// Modal
function openModal(title, sub, body) {{
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalSub').textContent = sub;
  document.getElementById('modalBody').innerHTML = body;
  document.getElementById('modalOverlay').classList.add('active');
}}
function closeModal() {{
  document.getElementById('modalOverlay').classList.remove('active');
}}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

// Animate bars on scroll
const observer = new IntersectionObserver(entries => {{
  entries.forEach(entry => {{
    if (entry.isIntersecting) {{
      entry.target.querySelectorAll('.bar-fill, .progress-fill').forEach(bar => {{
        const w = bar.style.width;
        bar.style.width = '0%';
        requestAnimationFrame(() => {{ bar.style.width = w; }});
      }});
      observer.unobserve(entry.target);
    }}
  }});
}}, {{ threshold: 0.2 }});
document.querySelectorAll('.card').forEach(card => observer.observe(card));
</script>

</body>
</html>"""

    return html
