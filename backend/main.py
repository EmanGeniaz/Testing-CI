import os, json, uuid, io, re, logging, traceback, concurrent.futures
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# ── Load .env ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse, ORJSONResponse
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

# ── LangChain imports ──────────────────────────────────────────────────────────
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException

from report_types import (
    DEFAULT_REPORT_TYPE_ID,
    ReportType,
    get_report_type,
    list_report_types,
)
from pptx_builder import build_report_pptx, build_data_pptx

# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

from data_snapshot import (
    resolve_data_dir,
    save_snapshot as _ds_save_snapshot,
    load_snapshot as _ds_load_snapshot,
    snapshot_status as _ds_snapshot_status,
)
from demo_runs import list_demos, get_demo, build_demo_session

# Resolve DATA_DIR up-front (used by both logging and the DB paths below) via
# the snapshot module's fallback chain so the rest of the file just sees a
# single resolved path.
_RESOLVED_DATA_DIR = resolve_data_dir()

_log_handlers = [logging.StreamHandler()]
try:
    LOG_PATH = _RESOLVED_DATA_DIR / "app.log"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _log_handlers.append(logging.FileHandler(LOG_PATH, encoding="utf-8"))
except OSError:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger("e_ai")

# ── NaN/Inf-safe + numpy-safe serialisation ────────────────────────────────────

def df_to_clean_records(df: pd.DataFrame) -> list:
    """DataFrame → list[dict] with NaN/numpy types resolved to plain Python via pandas JSON round-trip."""
    return json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))

# ═══════════════════════════════════════════════════════════════════════════════
#  CORS — pure ASGI middleware (outermost layer, catches everything including
#  errors that occur while streaming the request body)
# ═══════════════════════════════════════════════════════════════════════════════

CORS_HEADERS = {
    "access-control-allow-origin":  "*",
    "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
    "access-control-allow-headers": "*",
    "access-control-expose-headers": "*",
    "access-control-max-age":       "86400",
}

class CORSMiddleware:
    """Pure ASGI middleware — wraps the entire app, injects CORS on every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Preflight
            if scope.get("method") == "OPTIONS":
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(k.encode(), v.encode()) for k, v in CORS_HEADERS.items()],
                })
                await send({"type": "http.response.body", "body": b""})
                return

            # Intercept send to inject CORS headers on every response
            async def send_with_cors(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    existing = {h[0].lower() for h in headers}
                    for k, v in CORS_HEADERS.items():
                        if k.encode() not in existing:
                            headers.append((k.encode(), v.encode()))
                    message = {**message, "headers": headers}
                await send(message)

            try:
                await self.app(scope, receive, send_with_cors)
            except Exception as exc:
                log.error(f"Unhandled ASGI error: {exc}\n{traceback.format_exc()}")
                body = json.dumps({"detail": str(exc)}).encode()
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        *[(k.encode(), v.encode()) for k, v in CORS_HEADERS.items()],
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
        else:
            await self.app(scope, receive, send)

app = FastAPI(title="E-AI Media Intelligence API", default_response_class=ORJSONResponse)
app.add_middleware(CORSMiddleware)


# ── Exception handlers so HTTPException errors also carry CORS headers ─────────
@app.exception_handler(StarletteHTTPException)
async def cors_http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = await http_exception_handler(request, exc)
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response

@app.exception_handler(RequestValidationError)
async def cors_validation_exception_handler(request: Request, exc: RequestValidationError):
    response = await request_validation_exception_handler(request, exc)
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response

@app.exception_handler(Exception)
async def cors_generic_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled route error: {exc}\n{traceback.format_exc()}")
    response = JSONResponse(status_code=500, content={"detail": str(exc)})
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response

# ═══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = _RESOLVED_DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH   = DATA_DIR / "database.json"
RUNS_PATH = DATA_DIR / "runs.json"
RUNS_DIR  = DATA_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

log.info(f"DATA_DIR active: {DATA_DIR} (DB={DB_PATH}, RUNS={RUNS_PATH})")

# ── Snapshot wrappers — these are the public entry points the rest of the app
#    uses, so we can centralize the (data_dir, db_path, runs_path, runs_dir)
#    arguments and provide a swallow-errors guarantee for save.

def save_snapshot() -> Optional[Path]:
    """Persist the full DB + runs to a single snapshot JSON. Never raises."""
    try:
        return _ds_save_snapshot(DATA_DIR, DB_PATH, RUNS_PATH, RUNS_DIR)
    except Exception as e:
        log.error(f"save_snapshot wrapper failed: {e}")
        return None


def load_snapshot(force: bool = False) -> bool:
    """Restore the DB + runs from a snapshot if one exists. Never raises."""
    try:
        return _ds_load_snapshot(DATA_DIR, DB_PATH, RUNS_PATH, RUNS_DIR, force=force)
    except Exception as e:
        log.error(f"load_snapshot wrapper failed: {e}")
        return False


# Attempt snapshot restore on startup BEFORE the first request is served. The
# load is non-destructive by default (won't clobber existing DB files), so it
# is safe to call here even when an in-place DATA_DIR already has data.
try:
    load_snapshot()
except Exception as _snap_e:
    log.warning(f"Startup snapshot load skipped: {_snap_e}")
# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Failed to read {path}: {e}")
        return default

def _write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

def load_db()  -> dict: return _read_json(DB_PATH,   {"sessions": {}})
def save_db(d) -> None:  _write_json(DB_PATH, d)
def load_runs() -> dict: return _read_json(RUNS_PATH, {"runs": []})
def save_runs(d) -> None: _write_json(RUNS_PATH, d)

def get_session(session_id: str) -> dict:
    db = load_db()
    if session_id not in db["sessions"]:
        log.warning(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    return db["sessions"][session_id]

def update_session(session_id: str, payload: dict):
    db = load_db()
    if session_id not in db["sessions"]:
        db["sessions"][session_id] = {}
    db["sessions"][session_id].update(payload)
    # Track last-update time so /sessions can sort by recency
    db["sessions"][session_id]["updated_at"] = datetime.utcnow().isoformat()
    save_db(db)

# ═══════════════════════════════════════════════════════════════════════════════
#  LLM FACTORY  (falls back to .env if no key passed)
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm(provider: str, api_key: str = "", model: Optional[str] = None):
    provider = provider.lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        log.info(f"LLM: OpenAI model={mdl}")
        return ChatOpenAI(model=mdl, temperature=0, api_key=key)
    elif provider == "groq":
        from langchain_groq import ChatGroq
        key = api_key or os.getenv("GROQ_API_KEY", "")
        mdl = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        log.info(f"LLM: Groq model={mdl}")
        return ChatGroq(model=mdl, temperature=0, api_key=key)
    elif provider in ("claude", "anthropic"):
        from langchain_anthropic import ChatAnthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        mdl = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        log.info(f"LLM: Anthropic model={mdl}")
        return ChatAnthropic(model=mdl, temperature=0, api_key=key)
    elif provider in ("gemini", "google"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = api_key or os.getenv("GOOGLE_API_KEY", "")
        mdl = model or os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
        log.info(f"LLM: Gemini model={mdl}")
        return ChatGoogleGenerativeAI(model=mdl, temperature=0, google_api_key=key)
    else:
        raise ValueError(f"Unknown provider: {provider}")

# ═══════════════════════════════════════════════════════════════════════════════
#  FILE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _best_sheet(xl: pd.ExcelFile) -> pd.DataFrame:
    """Pick the sheet with the most rows, skip obviously empty/metadata sheets."""
    best_df, best_rows = None, -1
    for name in xl.sheet_names:
        try:
            df = xl.parse(name)
            df.dropna(how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)
            if len(df) > best_rows:
                best_df, best_rows = df, len(df)
        except Exception:
            continue
    return best_df if best_df is not None else xl.parse(xl.sheet_names[0])


def parse_upload(content: bytes, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower()
    log.info(f"Parsing file: {filename} ({len(content)} bytes, ext={ext})")
    try:
        if ext in ("xlsx", "xls", "xlsm", "xlsb"):
            engine = "pyxlsb" if ext == "xlsb" else None
            xl = pd.ExcelFile(io.BytesIO(content), engine=engine)
            df = _best_sheet(xl)
            # If first row looks like a header row of all-strings, pandas already used it
            df.columns = [str(c).strip() for c in df.columns]
            df = df.where(pd.notna(df), None)
            log.info(f"Excel ({ext}) parsed, sheet count={len(xl.sheet_names)}, shape={df.shape}")
            return df

        elif ext in ("csv", "tsv", "txt"):
            encodings = ("utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1")
            separators = (",", "\t", ";", "|")
            # Detect separator by sniffing the first 4KB
            sample = content[:4096]
            for enc in encodings:
                try:
                    text = sample.decode(enc)
                    # Count occurrences of each separator in non-quoted regions
                    counts = {sep: text.count(sep) for sep in separators}
                    detected_sep = max(counts, key=lambda s: counts[s])
                    if counts[detected_sep] == 0:
                        detected_sep = ","
                    df = pd.read_csv(
                        io.BytesIO(content),
                        encoding=enc,
                        sep=detected_sep,
                        engine="python",
                        on_bad_lines="skip",
                    )
                    # Drop entirely empty rows/cols
                    df.dropna(how="all", inplace=True)
                    df.dropna(axis=1, how="all", inplace=True)
                    df.columns = [str(c).strip() for c in df.columns]
                    df = df.where(pd.notna(df), None)
                    log.info(f"CSV parsed enc={enc} sep={repr(detected_sep)}, shape={df.shape}")
                    return df
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            raise ValueError("Could not decode file with any standard encoding")

        elif ext == "json":
            data = json.loads(content)
            if isinstance(data, dict):
                # Handle {data: [...]} or {results: [...]} wrappers
                for key in ("data", "results", "rows", "items", "records"):
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                else:
                    data = [data]
            df = pd.DataFrame(data)
            df = df.where(pd.notna(df), None)
            log.info(f"JSON parsed, shape={df.shape}")
            return df

        elif ext == "docx":
            from docx import Document
            doc = Document(io.BytesIO(content))
            rows = [{"text": p.text.strip()} for p in doc.paragraphs if p.text.strip()]
            df = pd.DataFrame(rows)
            log.info(f"DOCX parsed, {len(rows)} paragraphs")
            return df

        else:
            raise ValueError(f"Unsupported file type: .{ext}. Supported: xlsx, xls, csv, tsv, json, docx")
    except Exception as e:
        log.error(f"Parse error for {filename}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Could not parse {filename}: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  ROW ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _error_row(message: str, error_label: str = "Error") -> dict:
    """Minimal error sentinel — schema-agnostic. Aggregators / consumers should
    treat any dict with error=True as a failed row regardless of report type."""
    return {
        "error": True,
        "error_message": message,
        "_status": error_label,
    }


def analyse_row(llm, parser, prompt_template, report_type: ReportType,
                row_text: str, context: dict, row_idx: int) -> list[dict]:
    """Run one LLM tagging call. Returns a list of parsed-output dicts (one or
    more, depending on the report type's post_processor). Raw row merging is
    done by the caller so we don't need access to the full input row here."""
    import time
    import random
    chain = prompt_template | llm | parser
    log.info(f"  Analysing row {row_idx} ({report_type.id}): {row_text[:80]}…")

    max_retries = 5
    base_delay = 5.0

    for attempt in range(max_retries):
        try:
            result = chain.invoke({
                "brand_focus":        context.get("focus_brand", "Not specified"),
                "dataset_type":       context.get("dataset_type", "Mixed / unknown"),
                "additional_context": context.get("additional_context", "None provided"),
                "source_text":        row_text,
                "format_instructions": parser.get_format_instructions(),
            })
            data = result.model_dump()
            log.info(f"  Row {row_idx} parsed OK")
            return [data]
        except OutputParserException as e:
            log.error(f"  Row {row_idx} parse error: {e}")
            return [_error_row(f"⚠ Parse error: {str(e)[:300]}", "Parse Error")]
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate limit" in err_str or "quota" in err_str or "resource exhausted" in err_str:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    log.warning(f"  Row {row_idx} hit rate limit. Retrying in {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
            log.error(f"  Row {row_idx} unexpected error: {e}")
            return [_error_row(f"⚠ Unexpected error: {str(e)[:300]}", "Error")]

# ═══════════════════════════════════════════════════════════════════════════════
#  BATCH PROCESSING ENGINE
#  Strategy: concurrent batches of BATCH_SIZE rows, max MAX_WORKERS threads.
#  Good balance for LLM APIs: avoids rate limits, handles 1000-row files fine.
# ═══════════════════════════════════════════════════════════════════════════════

BATCH_SIZE  = int(os.getenv("BATCH_SIZE",  "5"))   # rows per concurrent batch
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))   # parallel threads per batch


def _cleanse_data(raw_data: list, text_col: str) -> tuple[list, dict]:
    """Clean raw data before tagging: remove duplicates, empty rows, and noise.
    Returns (cleaned_data, stats) where stats contains removal counts."""
    original_count = len(raw_data)
    removed_duplicates = 0
    removed_empty = 0
    removed_noise = 0

    seen_texts = set()
    cleaned = []

    for row in raw_data:
        text_value = str(row.get(text_col, "")).strip() if row.get(text_col) is not None else ""

        # Remove rows where text column is empty/null/whitespace
        if not text_value:
            removed_empty += 1
            continue

        # Remove rows that are too short (< 10 characters — likely noise)
        if len(text_value) < 10:
            removed_noise += 1
            continue

        # Remove exact duplicate rows (based on the text column)
        if text_value in seen_texts:
            removed_duplicates += 1
            continue

        # Remove rows that are obviously spam (repeated characters, all caps gibberish)
        # Check for repeated characters (e.g., "aaaaaaa" or "!!!!!!")
        if len(text_value) > 0:
            unique_chars = set(text_value.replace(" ", ""))
            # If the text has very few unique characters relative to length, it's likely spam
            if len(unique_chars) <= 3 and len(text_value) > 15:
                removed_noise += 1
                continue
            # Check for all-caps gibberish: all uppercase, no real words (very short words)
            if (text_value.isupper() and len(text_value) > 20
                    and all(len(w) <= 2 for w in text_value.split())):
                removed_noise += 1
                continue

        seen_texts.add(text_value)
        cleaned.append(row)

    stats = {
        "original": original_count,
        "cleaned": len(cleaned),
        "removed_duplicates": removed_duplicates,
        "removed_empty": removed_empty,
        "removed_noise": removed_noise,
    }
    return cleaned, stats

def _run_tagging_bg(session_id: str, provider: str, api_key: str,
                    model: Optional[str], session: dict, run_id: str,
                    report_type_id: str):
    start_time = datetime.utcnow()
    log.info(f"=== RUN {run_id} START | session={session_id} provider={provider} model={model} report_type={report_type_id} ===")

    try:
        report_type = get_report_type(report_type_id)
        llm    = get_llm(provider, api_key, model)
        parser = PydanticOutputParser(pydantic_object=report_type.schema)
        prompt = PromptTemplate(
            template=report_type.system_prompt,
            input_variables=report_type.prompt_variables,
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        schema_cfg = session["schema_config"]
        text_col   = schema_cfg["primary_text_column"]
        context    = session.get("dataset_context", {})
        raw_data   = session["raw_data"]

        # ── Data cleansing sub-agent ──────────────────────────────────────
        raw_data, cleanse_stats = _cleanse_data(raw_data, text_col)
        log.info(f"Run {run_id}: Data cleansing complete — "
                 f"original={cleanse_stats['original']}, "
                 f"cleaned={cleanse_stats['cleaned']}, "
                 f"removed_duplicates={cleanse_stats['removed_duplicates']}, "
                 f"removed_empty={cleanse_stats['removed_empty']}, "
                 f"removed_noise={cleanse_stats['removed_noise']}")

        # TEST_ROW_LIMIT caps the number of rows tagged per run. Set to a small
        # value (e.g. 20) on deployed/test environments to keep LLM costs bounded
        # while SMEs review output. 0 disables the cap.
        row_limit = int(os.getenv("TEST_ROW_LIMIT", "0"))
        if row_limit > 0 and len(raw_data) > row_limit:
            log.info(f"TEST_ROW_LIMIT={row_limit} → capping {len(raw_data)} rows to {row_limit}")
            raw_data = raw_data[:row_limit]

        total      = len(raw_data)

        # Determine concurrency and rate limits based on provider (Free Tiers)
        workers = MAX_WORKERS
        delay_between_requests = 0.0

        if provider == "groq":
            workers = 1
            delay_between_requests = 8.5 # Respect 6000 TPM
            log.info("Detected Groq: Adjusting to 1 worker and 8.5s delay to respect free tier TPM limits.")
        elif provider in ("gemini", "google"):
            workers = 1
            delay_between_requests = 4.2 # Respect 15 RPM
            log.info("Detected Gemini: Adjusting to 1 worker and 4.2s delay to respect 15 RPM free tier limit.")

        log.info(f"Run {run_id}: {total} rows, text_col='{text_col}', batch_size={BATCH_SIZE}, workers={workers}")

        # analyzed[i] is a list of output rows (1 or more) produced from input row i.
        # Most report types are 1:1 so lists have length 1; multi-finding report types
        # (Pharma SI) can return N rows from one input.
        analyzed: List[Optional[list]] = [None] * total

        def process_row(args):
            idx, row = args

            if delay_between_requests > 0:
                import time
                time.sleep(delay_between_requests)

            row_text = str(row.get(text_col, "")).strip()

            ai_cols = schema_cfg.get("ai_columns", [])
            other_cols_text = []
            for col in ai_cols:
                if col != text_col and col in row:
                    val = str(row[col]).strip()
                    if val and val != "None":
                        other_cols_text.append(f"{col}: {val}")

            if other_cols_text:
                extra_text = "\n".join(other_cols_text)
                if row_text:
                    row_text = f"{row_text}\n\n[Additional Context from other columns]\n{extra_text}"
                else:
                    row_text = f"[Additional Context from other columns]\n{extra_text}"

            if not row_text:
                row_text = " | ".join(str(v) for v in row.values() if v)

            parsed_list = analyse_row(llm, parser, prompt, report_type,
                                      row_text, context, idx)
            output_rows: list[dict] = []
            for parsed in parsed_list:
                if parsed.get("error"):
                    output_rows.append({**row, **parsed})
                else:
                    output_rows.extend(report_type.post_processor(row, parsed))
            return idx, output_rows

        def _flatten(analyzed_list):
            out = []
            for entry in analyzed_list:
                if entry:
                    out.extend(entry)
            return out

        # Process in batches to control concurrency
        completed = 0
        for batch_start in range(0, total, BATCH_SIZE * workers):
            batch_end  = min(batch_start + BATCH_SIZE * workers, total)
            batch_rows = [(i, raw_data[i]) for i in range(batch_start, batch_end)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(process_row, item): item[0] for item in batch_rows}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        idx, output_rows = fut.result()
                        analyzed[idx] = output_rows
                        completed += 1
                        progress = int(completed / total * 100)
                        # Save every row incrementally so frontend sees live updates
                        update_session(session_id, {
                            "analyzed_data": _flatten(analyzed),
                            "progress": progress,
                            "status": "running",
                        })
                        log.info(f"Run {run_id}: {completed}/{total} ({progress}%)")
                    except Exception as e:
                        orig_idx = futures[fut]
                        log.error(f"Run {run_id}: row {orig_idx} worker exception: {e}")
                        analyzed[orig_idx] = [{
                            **raw_data[orig_idx],
                            "error": True,
                            "error_message": f"⚠ Worker error: {str(e)[:200]}",
                            "_status": "Worker Error",
                        }]

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        final_data = _flatten(analyzed)

        update_session(session_id, {
            "analyzed_data": final_data,
            "progress": 100,
            "status": "complete",
            "run_id": run_id,
            "completed_at": datetime.utcnow().isoformat(),
        })

        # ── Persist run to runs.json index + individual runs/{run_id}.json ──
        run_meta = {
            "run_id":      run_id,
            "session_id":  session_id,
            "filename":    session.get("filename", ""),
            "provider":    provider,
            "model":       model or "default",
            "report_type": report_type_id,
            "total_rows":  total,
            "completed":   completed,
            "output_rows": len(final_data),
            "elapsed_sec": round(elapsed, 1),
            "status":      "complete",
            "started_at":  session.get("created_at", ""),
            "completed_at": datetime.utcnow().isoformat(),
            "context":     session.get("dataset_context", {}),
            "columns":     session.get("columns", []),
            "schema_config": session.get("schema_config", {}),
        }
        # Individual run file — contains full analyzed data
        _write_json(RUNS_DIR / f"{run_id}.json", {**run_meta, "analyzed_data": final_data})
        # Index file — lightweight, no row data
        runs = load_runs()
        runs["runs"].insert(0, run_meta)
        save_runs(runs)
        save_snapshot()
        log.info(f"=== RUN {run_id} COMPLETE | {completed}/{total} rows in {elapsed:.1f}s ===")

        # ── Auto-learn: save successful run as skill if novel ────────────
        try:
            skill_result = save_run_as_skill(session_id, run_meta)
            if skill_result:
                log.info(f"Auto-learned skill from run {run_id}: {skill_result.get('id')}")
        except Exception as learn_err:
            log.warning(f"Skill auto-learning failed (non-fatal): {learn_err}")

    except Exception as e:
        log.error(f"=== RUN {run_id} FAILED: {e}\n{traceback.format_exc()} ===")
        update_session(session_id, {"status": "error", "error_message": str(e)})
        err_meta = {
            "run_id": run_id, "session_id": session_id,
            "filename": session.get("filename", ""), "provider": provider,
            "model": model or "default",
            "report_type": report_type_id,
            "status": "error",
            "error": str(e), "started_at": session.get("created_at", ""),
            "completed_at": datetime.utcnow().isoformat(),
            "columns": session.get("columns", []),
            "schema_config": session.get("schema_config", {}),
        }
        _write_json(RUNS_DIR / f"{run_id}.json", {**err_meta, "analyzed_data": []})
        runs = load_runs()
        runs["runs"].insert(0, err_meta)
        save_runs(runs)

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    log.info("Health check")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat(),
            "batch_size": BATCH_SIZE, "max_workers": MAX_WORKERS}


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.post("/upload", response_class=ORJSONResponse)
async def upload_file(file: UploadFile = File(...)) -> ORJSONResponse:
    log.info(f"Upload: {file.filename} content_type={file.content_type}")
    content = await file.read()
    df = parse_upload(content, file.filename)

    records = df_to_clean_records(df)
    columns = list(df.columns)
    preview  = df_to_clean_records(df.head(4))

    session_id = str(uuid.uuid4())
    db = load_db()
    db["sessions"][session_id] = {
        "session_id": session_id,
        "filename":   file.filename,
        "columns":    columns,
        "raw_data":   records,
        "preview":    preview,
        "dataset_context": {},
        "schema_config":   {},
        "analyzed_data":   [],
        "status":     "uploaded",
        "created_at": datetime.utcnow().isoformat(),
    }
    save_db(db)
    save_snapshot()
    log.info(f"Uploaded: session={session_id} rows={len(records)} cols={columns}")

    return ORJSONResponse({
        "session_id": session_id,
        "filename":   file.filename,
        "columns":    columns,
        "row_count":  len(records),
        "preview":    preview,
    })


# ── Dataset context ────────────────────────────────────────────────────────────

class DatasetContextPayload(BaseModel):
    session_id: str
    dataset_type: str = "Single brand"
    focus_brand: str = ""
    additional_context: str = ""

@app.post("/context")
def set_context(payload: DatasetContextPayload):
    log.info(f"Context set: session={payload.session_id} type={payload.dataset_type}")
    update_session(payload.session_id, {"dataset_context": payload.model_dump(exclude={"session_id"})})
    return {"ok": True}


# ── Schema ─────────────────────────────────────────────────────────────────────

class SchemaConfigPayload(BaseModel):
    session_id: str
    primary_text_column: str
    visible_columns: list[str] = []
    ai_columns: list[str] = []

@app.post("/schema")
def set_schema(payload: SchemaConfigPayload):
    log.info(f"Schema set: session={payload.session_id} primary_col={payload.primary_text_column}")
    update_session(payload.session_id, {"schema_config": payload.model_dump(exclude={"session_id"})})
    return {"ok": True}


# ── Run tagging ────────────────────────────────────────────────────────────────

class RunTaggingPayload(BaseModel):
    session_id: str
    provider: str
    api_key: str = ""   # optional — falls back to .env
    model: Optional[str] = None
    report_type: str = DEFAULT_REPORT_TYPE_ID

@app.post("/run-tagging")
def run_tagging(payload: RunTaggingPayload, background_tasks: BackgroundTasks):
    session = get_session(payload.session_id)
    if not session.get("schema_config", {}).get("primary_text_column"):
        raise HTTPException(status_code=400, detail="Schema not configured — set primary_text_column first")

    try:
        get_report_type(payload.report_type)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run_id = str(uuid.uuid4())[:8]
    log.info(f"Starting run {run_id} for session {payload.session_id} report_type={payload.report_type}")
    update_session(payload.session_id, {
        "status": "running", "analyzed_data": [], "progress": 0,
        "run_id": run_id, "report_type": payload.report_type,
    })
    background_tasks.add_task(
        _run_tagging_bg,
        payload.session_id, payload.provider, payload.api_key,
        payload.model, session, run_id, payload.report_type,
    )
    return {"ok": True, "run_id": run_id, "message": "Tagging started"}


# ── Report types ───────────────────────────────────────────────────────────────

@app.get("/report-types")
def get_report_types():
    return {"report_types": list_report_types(),
            "default": DEFAULT_REPORT_TYPE_ID}


# ── Status / Results ───────────────────────────────────────────────────────────

@app.get("/session/{session_id}/status")
def get_status(session_id: str):
    s = get_session(session_id)
    return {
        "status":        s.get("status", "unknown"),
        "progress":      s.get("progress", 0),
        "total_rows":    len(s.get("raw_data", [])),
        "analyzed_rows": len(s.get("analyzed_data", [])),
        "run_id":        s.get("run_id"),
        "error_message": s.get("error_message"),
    }

@app.get("/session/{session_id}/results")
def get_results(session_id: str):
    s = get_session(session_id)
    return {
        "analyzed_data": s.get("analyzed_data", []),
        "columns":       s.get("columns", []),
        "schema_config": s.get("schema_config", {}),
    }

@app.get("/session/{session_id}")
def get_session_data(session_id: str):
    return get_session(session_id)

class RowUpdatePayload(BaseModel):
    col: str
    value: str

@app.patch("/session/{session_id}/row/{row_idx}")
def update_row(session_id: str, row_idx: int, payload: RowUpdatePayload):
    session = get_session(session_id)
    if "analyzed_data" not in session or not (0 <= row_idx < len(session["analyzed_data"])):
        raise HTTPException(status_code=404, detail="Row not found")
    
    session["analyzed_data"][row_idx][payload.col] = payload.value
    run_id = session.get("run_id")
    if run_id:
        run_file = RUNS_DIR / f"{run_id}.json"
        if run_file.exists():
            run_data = _read_json(run_file, {})
            if "analyzed_data" in run_data and 0 <= row_idx < len(run_data["analyzed_data"]):
                run_data["analyzed_data"][row_idx][payload.col] = payload.value
                _write_json(run_file, run_data)
                
    update_session(session_id, {"analyzed_data": session["analyzed_data"]})
    return {"ok": True}


# ── Run history ────────────────────────────────────────────────────────────────

@app.get("/runs")
def list_runs():
    runs = load_runs()
    return {"runs": runs.get("runs", [])}

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    """Return full run data (meta + analyzed_data) from individual run file."""
    run_file = RUNS_DIR / f"{run_id}.json"
    if run_file.exists():
        return _read_json(run_file, {})
    # Fallback: look up in index and try session
    runs = load_runs()
    run = next((r for r in runs.get("runs", []) if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        s = get_session(run["session_id"])
        return {**run, "analyzed_data": s.get("analyzed_data", []), "columns": s.get("columns", [])}
    except HTTPException:
        return {**run, "analyzed_data": [], "columns": []}

@app.get("/runs/{run_id}/results")
def get_run_results(run_id: str):
    """Alias for /runs/{run_id} — kept for backwards compatibility."""
    return get_run(run_id)


# ── Export ─────────────────────────────────────────────────────────────────────

@app.get("/session/{session_id}/export/csv")
def export_csv(session_id: str):
    s    = get_session(session_id)
    data = s.get("analyzed_data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No analyzed data yet")
    df  = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analysis_{session_id[:8]}.csv"'})

@app.get("/session/{session_id}/export/xlsx")
def export_xlsx(session_id: str):
    s    = get_session(session_id)
    data = s.get("analyzed_data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No analyzed data yet")
    df  = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Analysis")
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="analysis_{session_id[:8]}.xlsx"'})

@app.get("/session/{session_id}/export/json")
def export_json_file(session_id: str):
    s    = get_session(session_id)
    data = s.get("analyzed_data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No analyzed data yet")
    return StreamingResponse(iter([json.dumps(data, indent=2, default=str)]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="analysis_{session_id[:8]}.json"'})


@app.get("/session/{session_id}/export/pptx")
def export_pptx(session_id: str):
    """Export tagged data as a PPTX table presentation (raw data in slides)."""
    s = get_session(session_id)
    data = s.get("analyzed_data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No analyzed data yet")
    filename = s.get("filename", "data")
    pptx_bytes = build_data_pptx(data, filename)
    return StreamingResponse(
        iter([pptx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}_data.pptx"'},
    )


@app.get("/session/{session_id}/export/pptx-report")
def export_pptx_report(session_id: str):
    """Export a polished PPTX report presentation generated from tagged analysis data."""
    session = get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])
    if not analyzed_data:
        raise HTTPException(status_code=404, detail="No analyzed data yet. Run tagging first.")

    # Generate report data inline (same logic as the generate-report endpoint)
    report_data = _generate_fallback_report(session, analyzed_data)

    # Try LLM-based report if possible (best effort — fall back to statistical)
    try:
        payload = GenerateReportPayload()
        llm, provider_name = _resolve_llm_for_report(session, payload)
        if llm is not None:
            context = session.get("dataset_context", {})
            report_type_id = session.get("report_type", DEFAULT_REPORT_TYPE_ID)
            stats = _collect_tag_stats(analyzed_data)
            stats_text = _build_stats_text(stats)
            sample_text = _build_sample_data(session, analyzed_data, max_samples=20)

            prompt_text = REPORT_GENERATION_PROMPT.format(
                filename=session.get("filename", "Dataset"),
                report_type=report_type_id,
                brand_focus=context.get("focus_brand", "Not specified"),
                dataset_type=context.get("dataset_type", "Not specified"),
                additional_context=context.get("additional_context", "None"),
                total_items=stats["total_rows"] - stats["error_rows"],
                tag_stats=stats_text,
                sample_data=sample_text,
            )
            response = llm.invoke(prompt_text)
            raw_content = response.content if hasattr(response, "content") else str(response)
            report_data = _parse_llm_report_json(raw_content)

            # Retry if first attempt produced no findings
            if not report_data.get("findings") and len(raw_content) > 100:
                log.warning("PPTX export: first LLM call produced unparseable JSON, retrying")
                retry_prompt = REPORT_GENERATION_RETRY_PROMPT.format(
                    filename=session.get("filename", "Dataset"),
                    report_type=report_type_id,
                    brand_focus=context.get("focus_brand", "Not specified"),
                    total_items=stats["total_rows"] - stats["error_rows"],
                    tag_stats=stats_text,
                )
                retry_response = llm.invoke(retry_prompt)
                retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
                retry_data = _parse_llm_report_json(retry_content)
                if retry_data.get("findings"):
                    report_data = retry_data

            # Ensure metadata
            if "metadata" not in report_data:
                report_data["metadata"] = {}
            valid = stats["total_rows"] - stats["error_rows"]
            report_data["metadata"]["items_reviewed"] = valid
            report_data["metadata"]["report_type"] = report_type_id
            report_data["metadata"]["generated_at"] = datetime.utcnow().isoformat()
            report_data["metadata"]["method"] = "llm"
            report_data["metadata"]["provider"] = provider_name
    except Exception as e:
        log.warning(f"LLM report generation failed for PPTX export, using fallback: {e}")
        # report_data already has the fallback

    # Build the PPTX
    filename = session.get("filename", "report")
    pptx_bytes = build_report_pptx(report_data, analyzed_data)
    return StreamingResponse(
        iter([pptx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}_report.pptx"'},
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

class GenerateReportPayload(BaseModel):
    provider: Optional[str] = None
    api_key: str = ""
    model: Optional[str] = None


def _collect_tag_stats(analyzed_data: list[dict]) -> dict:
    """Gather frequency counts for themes, sentiments, signals, drivers, etc.
    from the analyzed data rows. Works across all report types by inspecting
    whichever standard tag keys are present."""
    from collections import Counter

    stats: dict = {
        "total_rows": len(analyzed_data),
        "error_rows": 0,
        "themes": Counter(),
        "sentiments": Counter(),
        "sentiment_nuances": Counter(),
        "emotions": Counter(),
        "signals": Counter(),
        "drivers": Counter(),
        "brands": Counter(),
        "severities": [],
        "confidences": [],
        # Pharma SI specific
        "stages": Counter(),
        "unmet_needs": Counter(),
        "concerns": Counter(),
        "qol_impacts": Counter(),
        "reporter_types": Counter(),
        # GenZ specific
        "engagement_drivers": Counter(),
        "purchase_intents": Counter(),
        "loyalty_levels": Counter(),
    }

    for row in analyzed_data:
        if row.get("error"):
            stats["error_rows"] += 1
            continue

        # Common fields across report types
        if row.get("theme"):
            stats["themes"][row["theme"]] += 1
        if row.get("sentiment"):
            stats["sentiments"][row["sentiment"]] += 1
        if row.get("sentiment_nuance"):
            stats["sentiment_nuances"][row["sentiment_nuance"]] += 1
        if row.get("emotion"):
            stats["emotions"][row["emotion"]] += 1
        if row.get("driver"):
            stats["drivers"][row["driver"]] += 1
        if row.get("brand"):
            stats["brands"][row["brand"]] += 1
        if row.get("primary_brand"):
            stats["brands"][row["primary_brand"]] += 1

        # Signals — may be comma-separated
        sig_val = row.get("signals", "")
        if sig_val and isinstance(sig_val, str):
            for sig in sig_val.split(","):
                sig = sig.strip()
                if sig:
                    stats["signals"][sig] += 1

        # Numeric fields
        if "severity" in row:
            try:
                stats["severities"].append(int(row["severity"]))
            except (ValueError, TypeError):
                pass
        if "confidence" in row:
            try:
                stats["confidences"].append(float(row["confidence"]))
            except (ValueError, TypeError):
                pass

        # Pharma SI fields
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

        # GenZ fields
        if row.get("engagement_driver"):
            stats["engagement_drivers"][row["engagement_driver"]] += 1
        if row.get("purchase_intent"):
            stats["purchase_intents"][row["purchase_intent"]] += 1
        if row.get("brand_loyalty_level"):
            stats["loyalty_levels"][row["brand_loyalty_level"]] += 1

    return stats


def _top_n(counter, n: int = 5) -> list[tuple]:
    """Return the top-n items from a Counter as (key, count) tuples."""
    if not counter:
        return []
    return counter.most_common(n)


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{count / total * 100:.0f}%"


def _generate_fallback_report(session: dict, analyzed_data: list[dict]) -> dict:
    """Generate a statistical summary report without calling an LLM.
    Used when no LLM API key is available."""
    stats = _collect_tag_stats(analyzed_data)
    total = stats["total_rows"]
    errors = stats["error_rows"]
    valid = total - errors
    filename = session.get("filename", "Dataset")
    context = session.get("dataset_context", {})
    report_type_id = session.get("report_type", DEFAULT_REPORT_TYPE_ID)

    # Build top themes text
    top_themes = _top_n(stats["themes"], 5)
    top_sentiments = _top_n(stats["sentiments"])
    top_signals = _top_n(stats["signals"], 5)
    top_drivers = _top_n(stats["drivers"], 5)

    # Sentiment distribution text
    sent_lines = []
    for sent, cnt in top_sentiments:
        sent_lines.append(f"**{sent}**: {cnt} ({_pct(cnt, valid)})")
    sentiment_text = ", ".join(sent_lines) if sent_lines else "No sentiment data"

    # Theme distribution text
    theme_lines = []
    for theme, cnt in top_themes:
        theme_lines.append(f"**{theme}**: {cnt} ({_pct(cnt, valid)})")
    theme_text = "; ".join(theme_lines) if theme_lines else "No theme data"

    # Executive summary
    top_theme_name = top_themes[0][0] if top_themes else "N/A"
    top_theme_count = top_themes[0][1] if top_themes else 0
    top_sent_name = top_sentiments[0][0] if top_sentiments else "N/A"
    top_sent_count = top_sentiments[0][1] if top_sentiments else 0

    avg_severity = ""
    if stats["severities"]:
        avg_sev = sum(stats["severities"]) / len(stats["severities"])
        avg_severity = f" Average severity: **{avg_sev:.1f}/10**."

    avg_confidence = ""
    if stats["confidences"]:
        avg_conf = sum(stats["confidences"]) / len(stats["confidences"])
        avg_confidence = f" Average confidence: **{avg_conf:.2f}**."

    exec_summary = (
        f"Analysis of **{valid}** items from *{filename}*. "
        f"The dominant theme is **{top_theme_name}** "
        f"({_pct(top_theme_count, valid)} of items). "
        f"Sentiment skews **{top_sent_name}** "
        f"({_pct(top_sent_count, valid)}).{avg_severity}{avg_confidence}"
    )

    # Build sections
    sections = [
        {
            "id": "the-read",
            "heading": "The read",
            "body": exec_summary,
        },
        {
            "id": "theme-distribution",
            "heading": "Theme distribution",
            "body": theme_text,
        },
        {
            "id": "sentiment-breakdown",
            "heading": "Sentiment breakdown",
            "body": sentiment_text,
        },
    ]

    # Signals section
    if top_signals:
        sig_lines = [f"**{s}**: {c} ({_pct(c, valid)})" for s, c in top_signals]
        sections.append({
            "id": "signal-distribution",
            "heading": "Signals detected",
            "body": "; ".join(sig_lines),
        })

    # Drivers section
    if top_drivers:
        drv_lines = [f"**{d}**: {c}" for d, c in top_drivers]
        sections.append({
            "id": "driver-distribution",
            "heading": "Top narrative drivers",
            "body": "; ".join(drv_lines),
        })

    # Pharma-specific sections
    if stats["stages"]:
        stage_lines = [f"**{s}**: {c}" for s, c in _top_n(stats["stages"])]
        sections.append({
            "id": "disease-stages",
            "heading": "Disease stages",
            "body": "; ".join(stage_lines),
        })
    if stats["unmet_needs"]:
        need_lines = [f"**{n}**: {c}" for n, c in _top_n(stats["unmet_needs"], 5)]
        sections.append({
            "id": "unmet-needs",
            "heading": "Unmet needs",
            "body": "; ".join(need_lines),
        })

    # Build findings from top themes
    findings = []
    for i, (theme, cnt) in enumerate(top_themes, start=1):
        # Determine confidence based on frequency
        freq_ratio = cnt / valid if valid > 0 else 0
        if freq_ratio >= 0.2:
            conf = "high"
        elif freq_ratio >= 0.1:
            conf = "medium"
        else:
            conf = "low"

        findings.append({
            "number": i,
            "confidence": conf,
            "claim": f"*{theme}* is a {'dominant' if freq_ratio >= 0.2 else 'notable'} theme, appearing in {_pct(cnt, valid)} of analyzed items",
            "support": f"Found in {cnt} of {valid} items. "
                       + (f"Most common sentiment in this theme cluster: {top_sent_name}." if top_sentiments else ""),
        })

    # Build evidence from actual data rows (pick representative quotes)
    evidence = []
    seen_themes = set()
    for row in analyzed_data:
        if row.get("error"):
            continue
        row_theme = row.get("theme", "")
        if not row_theme or row_theme in seen_themes:
            continue
        seen_themes.add(row_theme)

        # Try to get a verbatim quote
        quote = (
            row.get("xai_text_evidence", "")
            or row.get("theme_verbatim", "")
            or row.get("qol_verbatim", "")
            or ""
        )
        if not quote:
            # Fall back to source text column
            schema_cfg = session.get("schema_config", {})
            text_col = schema_cfg.get("primary_text_column", "")
            if text_col and text_col in row:
                source = str(row[text_col])
                quote = source[:300] + ("..." if len(source) > 300 else "")

        if quote:
            tags = [row_theme]
            if row.get("sentiment"):
                tags.append(row["sentiment"])
            evidence.append({
                "source": session.get("filename", "Dataset"),
                "quote": quote,
                "tags": tags,
                "sentiment": row.get("sentiment", "Unknown"),
            })
        if len(evidence) >= 10:
            break

    # Build title
    focus = context.get("focus_brand", "")
    title_brand = focus if focus else filename
    title_headline = f"{top_theme_name} dominates" if top_themes else "Statistical summary"
    title = f"{title_brand} — {title_headline}"

    # Recommendations
    so_what_parts = []
    if top_themes:
        so_what_parts.append(
            f"The most frequent theme is **{top_themes[0][0]}** — prioritize monitoring and response strategies around this area."
        )
    if top_sentiments and top_sentiments[0][0] == "Negative":
        so_what_parts.append(
            "Negative sentiment is dominant — consider proactive communication or crisis preparedness."
        )
    elif top_sentiments and top_sentiments[0][0] == "Positive":
        so_what_parts.append(
            "Positive sentiment is dominant — leverage this for brand advocacy and amplification."
        )
    if top_signals:
        so_what_parts.append(
            f"Key signals to watch: {', '.join(s for s, _ in top_signals[:3])}."
        )
    if not so_what_parts:
        so_what_parts.append("Review the tagged data for deeper qualitative insights.")

    return {
        "title": title,
        "subtitle": f"Statistical summary of {valid} analyzed items from {filename}",
        "metadata": {
            "period": context.get("additional_context", "Not specified"),
            "items_reviewed": valid,
            "report_type": report_type_id,
            "generated_at": datetime.utcnow().isoformat(),
            "method": "statistical_fallback",
        },
        "sections": sections,
        "findings": findings,
        "evidence": evidence,
        "so_what": " ".join(so_what_parts),
    }


REPORT_GENERATION_PROMPT = """You are a senior strategy consultant briefing a brand/medical/comms leadership team. You do not write summaries — you write the read. Your output sounds like a sharp principal at a top-tier consultancy: punchy, opinionated, evidence-driven, and ruthlessly focused on the "so what."

CONTEXT:
- Dataset: {filename}
- Report Type: {report_type}
- Brand/Focus: {brand_focus}
- Dataset Type: {dataset_type}
- Additional Context: {additional_context}
- Total Items Analyzed: {total_items}

TAG STATISTICS:
{tag_stats}

SAMPLE TAGGED DATA (representative rows):
{sample_data}

═══════════════════════════════════════════════════════════════════════════════
RESPONSE FORMAT RULES — READ CAREFULLY:
1. Your response must be ONLY a JSON object.
2. Do NOT wrap the JSON in markdown code fences (no ```json, no ```).
3. Do NOT include ANY text before the opening {{ or after the closing }}.
4. Do NOT include any explanation, preamble, commentary, or notes.
5. The very first character of your response MUST be {{ and the very last character MUST be }}.
═══════════════════════════════════════════════════════════════════════════════

The JSON object must have exactly these keys:
"title", "subtitle", "executive_one_liner", "sections", "findings", "evidence", "talkable_stats", "so_what".

STRUCTURE:

- "title": string — "<Brand/Dataset> — <punchy strategic headline>". Not a description. A POV.
  GOOD: "Nuvaxovid — Trust is built in the comments, not the trial data"
  BAD:  "Nuvaxovid Social Listening Analysis Report"

- "subtitle": string — one sentence that frames the strategic stakes.
  GOOD: "Patient confidence is forming around real-world tolerability stories, not efficacy numbers — which means the comms playbook is wrong."
  BAD:  "An analysis of social conversations about Nuvaxovid in Q3."

- "executive_one_liner": string — a SINGLE sentence that captures the entire story. If a CMO read only this line, they would know the strategic call.
  GOOD: "Diagnosis is the battleground: 52% of unmet need and 50% of concerns converge on speed and awareness — not treatment."
  BAD:  "There are several themes in the data including diagnosis, treatment, and support."

- "sections": array of EXACTLY 3 objects, each with "id", "heading", "body" (string, 3-5 sentences, use **bold** for key stats):
    1. {{"id": "the-read", "heading": "The Read", "body": "..."}}
       — Overall narrative. What is the story the data is telling? State your POV in the first sentence.
    2. {{"id": "convergence-signals", "heading": "Convergence Signals", "body": "..."}}
       — Where do multiple data dimensions agree? (e.g., "Theme X + Sentiment Y + Driver Z all point to ___"). This is where you prove the read isn't a one-variable artifact.
    3. {{"id": "hidden-pattern", "heading": "The Hidden Pattern", "body": "..."}}
       — The counter-intuitive finding. Something that contradicts the obvious read, or a quiet signal a junior analyst would miss. State why it matters strategically.

- "findings": array of 6-8 objects. Each finding is a unit of strategic argument:
    {{
      "number": <int 1..N>,
      "confidence": "high" | "medium" | "low",
      "claim": "<one sentence POV in punchy consultant voice, with *italics* for the strategic verb/noun>",
      "support": "<evidence WITH numbers: cite tag counts, percentages, theme co-occurrence>",
      "so_what": "<one specific implication for brand/medical/comms strategy — name the action, not the abstraction>"
    }}
  Rules:
    • Finding #1 is the HEADLINE INSIGHT. It must match the executive_one_liner's thrust.
    • Confidence is EARNED, not guessed:
        - "high"   ⇒ supported by ≥40 items OR ≥25% of dataset AND corroborated across ≥2 dimensions
        - "medium" ⇒ supported by ≥15 items OR ≥10% of dataset
        - "low"    ⇒ smaller signal, directional only — say so in the claim
    • Each claim must connect data → business implication.
    • NEVER say "is a notable theme" — say WHY it's notable and what it means.

- "evidence": array of 8-12 objects — verbatim quotes that are vivid and quote-worthy:
    {{
      "source": "<Patient | Caregiver | HCP> · <Platform e.g. Reddit/X/Forum> · <Stage e.g. Pre-Dx/Dx/Tx/Post-Tx>",
      "quote": "<verbatim string from sample data — do NOT paraphrase>",
      "tags": ["<tag1>", "<tag2>"],
      "sentiment": "positive" | "negative" | "neutral" | "mixed"
    }}
  Filter ruthlessly:
    • REJECT generic statements ("I had a hard time"). Pick quotes with specificity, emotion, or imagery.
    • REJECT near-duplicates. If two quotes say the same thing, pick the more vivid one.
    • Each quote should be quotable in a board deck.
    • Source attribution must be inferred from the data (e.g., subreddit, author role, post stage). If unknown, use best inference + "(inferred)".

- "talkable_stats": array of EXACTLY 5 strings — memorable, quote-worthy statistics a strategist would put on a slide.
  Format: "<stat with number> — <one-clause interpretation>"
  GOOD: "52% of unmet-need posts mention diagnostic delay — speed-to-Dx is the single biggest patient pain"
  BAD:  "There were 52 mentions of diagnosis."

- "so_what": array of 3-4 strings — each a SPECIFIC recommendation tied to a function (Brand / Medical / Comms / Patient Services).
  Format: "<Function>: <imperative action> — <one-clause rationale tied to a finding>"
  GOOD: "Comms: Reframe HCP materials around time-to-diagnosis benchmarks, not mechanism-of-action — Finding #1 shows MoA messaging is invisible in patient discourse."
  BAD:  "Consider exploring opportunities to communicate more effectively about diagnosis."

═══════════════════════════════════════════════════════════════════════════════
HARD ANTI-PATTERNS — your output will be rejected if it contains:
- "is a notable theme" / "is a recurring theme" / "is a key theme"
- "essentially" / "fundamentally" / "it's worth noting" / "in essence" / "ultimately"
- "consider exploring" / "may want to think about" / "could potentially"
- Restating a number without interpretation ("19% mentioned diagnosis." ← what does that MEAN?)
- Generic recommendations not tied to a function or finding
- Fabricated quotes, fabricated numbers, fabricated tags
═══════════════════════════════════════════════════════════════════════════════

EXAMPLES — GOOD vs BAD:

BAD finding:
  {{"claim": "Diagnostic Challenges is a notable theme appearing in 19% of items.",
    "support": "19% of tagged items mention diagnostic challenges.",
    "so_what": "Consider exploring this theme further."}}

GOOD finding:
  {{"claim": "Diagnosis *dominates* the patient burden — and it isn't the disease, it's the wait.",
    "support": "52% of unmet-need posts cite diagnostic delay; 50% of negative-sentiment posts converge on awareness gaps in primary care. The two clusters overlap on 38% of items — they are the same story told twice.",
    "so_what": "Brand: shift the lead message from treatment efficacy to time-to-diagnosis — the audience already accepts the drug works, they don't trust the system to identify them in time."}}

BAD section body:
  "Sentiment was mostly negative. Many users expressed frustration. Diagnosis was a theme."

GOOD section body:
  "Patients aren't angry at the drug — they're angry at the **18-month diagnostic odyssey** that precedes it. **52%** of unmet-need posts and **50%** of negative-sentiment posts independently land on the same culprit: primary-care recognition. The brand's current MoA-led narrative is solving a problem the audience hasn't asked about yet."

═══════════════════════════════════════════════════════════════════════════════
CONTENT INTEGRITY RULES:
- Ground EVERY number in the TAG STATISTICS block. Do NOT invent numbers.
- Evidence quotes MUST be verbatim from SAMPLE TAGGED DATA. Do NOT fabricate.
- Use **bold** for emphasis in section bodies, *italics* in finding claims.
- Write like a person. Cut filler. Cut hedging. Earn every sentence.

REMEMBER: Output ONLY the raw JSON object. First character: {{ — Last character: }}"""

REPORT_GENERATION_RETRY_PROMPT = """Your previous response could not be parsed as JSON. You will now return ONLY valid JSON. No exceptions.

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE FORMAT RULES — VIOLATION = REJECTION:
- First character of your response: {{
- Last character of your response: }}
- NO markdown. NO code fences. NO backticks. NO ```json. NO ```.
- NO preamble. NO "Here is the JSON:". NO "Sure, here you go:". NO commentary.
- NO trailing text. NO notes. NO explanations after the closing brace.
- All strings must be double-quoted. All keys must be double-quoted.
- No trailing commas. No comments (// or /* */). No NaN or Infinity.
- Escape internal double quotes inside string values with \\".
═══════════════════════════════════════════════════════════════════════════════

The JSON object MUST contain exactly these keys (no more, no fewer):
  "title", "subtitle", "executive_one_liner", "sections", "findings", "evidence", "talkable_stats", "so_what"

REQUIRED SHAPES:
- "title": string
- "subtitle": string
- "executive_one_liner": string (single sentence)
- "sections": array of 3 objects, each {{"id": str, "heading": str, "body": str}}.
    Section ids MUST be: "the-read", "convergence-signals", "hidden-pattern".
- "findings": array of 6-8 objects, each {{"number": int, "confidence": "high"|"medium"|"low", "claim": str, "support": str, "so_what": str}}.
- "evidence": array of 8-12 objects, each {{"source": str, "quote": str, "tags": [str,...], "sentiment": "positive"|"negative"|"neutral"|"mixed"}}.
- "talkable_stats": array of 5 strings.
- "so_what": array of 3-4 strings.

VOICE: senior consultant. Punchy. Strategic. Connects data to business implications. No filler ("essentially", "fundamentally", "it's worth noting", "consider exploring"). No "is a notable theme".

CONTEXT:
- Dataset: {filename}
- Report Type: {report_type}
- Brand/Focus: {brand_focus}
- Total Items: {total_items}

TAG STATISTICS:
{tag_stats}

Ground every number in the statistics above. Do NOT invent numbers or quotes.

Return ONLY the JSON object now — first character must be {{ :"""


def _build_stats_text(stats: dict) -> str:
    """Format tag statistics into a readable text block for the LLM prompt."""
    lines = []
    total = stats["total_rows"]
    errors = stats["error_rows"]
    valid = total - errors

    lines.append(f"Total rows: {total} (valid: {valid}, errors: {errors})")

    if stats["themes"]:
        lines.append("\nTheme distribution:")
        for theme, cnt in _top_n(stats["themes"], 10):
            lines.append(f"  - {theme}: {cnt} ({_pct(cnt, valid)})")

    if stats["sentiments"]:
        lines.append("\nSentiment distribution:")
        for sent, cnt in _top_n(stats["sentiments"]):
            lines.append(f"  - {sent}: {cnt} ({_pct(cnt, valid)})")

    if stats["sentiment_nuances"]:
        lines.append("\nSentiment nuances:")
        for nuance, cnt in _top_n(stats["sentiment_nuances"], 8):
            lines.append(f"  - {nuance}: {cnt}")

    if stats["emotions"]:
        lines.append("\nEmotions:")
        for emo, cnt in _top_n(stats["emotions"], 8):
            lines.append(f"  - {emo}: {cnt}")

    if stats["signals"]:
        lines.append("\nSignals detected:")
        for sig, cnt in _top_n(stats["signals"], 10):
            lines.append(f"  - {sig}: {cnt} ({_pct(cnt, valid)})")

    if stats["drivers"]:
        lines.append("\nNarrative drivers:")
        for drv, cnt in _top_n(stats["drivers"], 10):
            lines.append(f"  - {drv}: {cnt}")

    if stats["brands"]:
        lines.append("\nBrands mentioned:")
        for brand, cnt in _top_n(stats["brands"], 10):
            lines.append(f"  - {brand}: {cnt}")

    if stats["severities"]:
        avg_sev = sum(stats["severities"]) / len(stats["severities"])
        max_sev = max(stats["severities"])
        lines.append(f"\nSeverity: avg={avg_sev:.1f}, max={max_sev}")

    if stats["confidences"]:
        avg_conf = sum(stats["confidences"]) / len(stats["confidences"])
        lines.append(f"Confidence: avg={avg_conf:.2f}")

    # Pharma SI fields
    if stats["stages"]:
        lines.append("\nDisease stages:")
        for stage, cnt in _top_n(stats["stages"]):
            lines.append(f"  - {stage}: {cnt}")

    if stats["unmet_needs"]:
        lines.append("\nUnmet needs:")
        for need, cnt in _top_n(stats["unmet_needs"], 8):
            lines.append(f"  - {need}: {cnt}")

    if stats["concerns"]:
        lines.append("\nConcerns:")
        for concern, cnt in _top_n(stats["concerns"], 8):
            lines.append(f"  - {concern}: {cnt}")

    if stats["qol_impacts"]:
        lines.append("\nQoL impacts:")
        for qol, cnt in _top_n(stats["qol_impacts"]):
            lines.append(f"  - {qol}: {cnt}")

    if stats["reporter_types"]:
        lines.append("\nReporter types:")
        for rt, cnt in _top_n(stats["reporter_types"]):
            lines.append(f"  - {rt}: {cnt}")

    # GenZ fields
    if stats["engagement_drivers"]:
        lines.append("\nEngagement drivers:")
        for drv, cnt in _top_n(stats["engagement_drivers"], 8):
            lines.append(f"  - {drv}: {cnt}")

    if stats["purchase_intents"]:
        lines.append("\nPurchase intents:")
        for pi, cnt in _top_n(stats["purchase_intents"]):
            lines.append(f"  - {pi}: {cnt}")

    if stats["loyalty_levels"]:
        lines.append("\nLoyalty levels:")
        for ll, cnt in _top_n(stats["loyalty_levels"]):
            lines.append(f"  - {ll}: {cnt}")

    return "\n".join(lines)


def _build_sample_data(session: dict, analyzed_data: list[dict], max_samples: int = 20) -> str:
    """Build a text block of representative sample rows for the LLM.
    Picks a diverse set across themes/sentiments."""
    schema_cfg = session.get("schema_config", {})
    text_col = schema_cfg.get("primary_text_column", "")

    # Collect non-error rows
    valid_rows = [r for r in analyzed_data if not r.get("error")]
    if not valid_rows:
        return "No valid analyzed data available."

    # Pick a diverse sample: try to cover different themes
    seen_themes = set()
    selected = []

    # First pass: one per theme
    for row in valid_rows:
        theme = row.get("theme", "")
        if theme and theme not in seen_themes:
            seen_themes.add(theme)
            selected.append(row)
            if len(selected) >= max_samples:
                break

    # Fill remaining slots with other rows
    if len(selected) < max_samples:
        for row in valid_rows:
            if row not in selected:
                selected.append(row)
                if len(selected) >= max_samples:
                    break

    lines = []
    for i, row in enumerate(selected, 1):
        parts = [f"--- Sample {i} ---"]

        # Source text
        if text_col and text_col in row:
            source = str(row[text_col])
            if len(source) > 500:
                source = source[:500] + "..."
            parts.append(f"Text: {source}")

        # Key tags
        for key in ("theme", "sentiment", "sentiment_nuance", "emotion",
                     "driver", "signals", "severity", "confidence", "brand",
                     "primary_brand",
                     # Pharma SI
                     "stage", "unmet_need", "concern", "qol_impact",
                     "reporter_type",
                     # GenZ
                     "engagement_driver", "purchase_intent",
                     "brand_loyalty_level"):
            val = row.get(key)
            if val and str(val).strip() and str(val).strip() != "None":
                parts.append(f"{key}: {val}")

        # Evidence quotes
        for key in ("xai_text_evidence", "theme_verbatim",
                     "unmet_need_verbatim", "concern_verbatim", "qol_verbatim"):
            val = row.get(key)
            if val and str(val).strip():
                parts.append(f"evidence ({key}): {val}")

        lines.append("\n".join(parts))

    return "\n\n".join(lines)


def _try_parse_json(text: str) -> dict | None:
    """Try to parse a string as JSON, returning None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def _fix_common_json_issues(text: str) -> str:
    """Apply common fixes to malformed JSON strings."""
    fixed = text
    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([\]}])", r"\1", fixed)
    # Fix unescaped newlines inside string values
    fixed = re.sub(r'(?<=": ")([^"]*?)(\n)([^"]*?)(?=")', lambda m: m.group(0).replace('\n', '\\n'), fixed)
    # Remove control characters that break JSON
    fixed = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fixed)
    return fixed


def _parse_llm_report_json(raw_text: str) -> dict:
    """Extract and parse JSON from the LLM response, handling markdown fences
    and other common LLM response quirks. If all parsing fails, constructs a
    minimal valid report from whatever text was returned."""
    if not raw_text or not raw_text.strip():
        log.warning("Empty LLM response received")
        return _build_minimal_fallback_report("")

    text = raw_text.strip()

    # ── Strategy 1: Direct parse (ideal case — LLM followed instructions) ─
    result = _try_parse_json(text)
    if result:
        return result

    # ── Strategy 2: Strip markdown code fences (```json ... ```) ──────────
    # Handle various fence styles: ```json, ``` json, ```JSON, etc.
    cleaned = re.sub(r"^```\s*(?:json|JSON)?\s*\n?", "", text)
    cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned).strip()
    result = _try_parse_json(cleaned)
    if result:
        return result

    # ── Strategy 3: Extract JSON between first { and last } ──────────────
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text[brace_start:brace_end + 1]

        result = _try_parse_json(candidate)
        if result:
            return result

        # ── Strategy 4: Fix common JSON issues and retry ─────────────────
        fixed = _fix_common_json_issues(candidate)
        result = _try_parse_json(fixed)
        if result:
            return result

        # ── Strategy 5: Balanced brace matching ──────────────────────────
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    balanced = text[brace_start:i + 1]
                    result = _try_parse_json(balanced)
                    if result:
                        return result
                    result = _try_parse_json(_fix_common_json_issues(balanced))
                    if result:
                        return result
                    break

    # ── Strategy 6: Find JSON inside any code fence block in the text ────
    fence_patterns = [
        r"```\s*(?:json|JSON)\s*\n(.*?)\n\s*```",
        r"```\s*\n(.*?)\n\s*```",
        r"`(\\{.*?\\})`",
    ]
    for pattern in fence_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            result = _try_parse_json(match.group(1).strip())
            if result:
                return result
            result = _try_parse_json(_fix_common_json_issues(match.group(1).strip()))
            if result:
                return result

    # ── Strategy 7: Try to find multiple JSON objects and merge ───────────
    # Some LLMs split JSON across multiple blocks
    json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    for block in json_blocks:
        result = _try_parse_json(block)
        if result and any(k in result for k in ("title", "sections", "findings")):
            return result

    # ── Strategy 8: Construct a minimal valid report from raw text ────────
    log.warning(f"All JSON parsing strategies failed. Constructing minimal report from raw text. "
                f"First 300 chars: {raw_text[:300]}")
    return _build_minimal_fallback_report(raw_text)


def _build_minimal_fallback_report(raw_text: str) -> dict:
    """Construct a minimal valid report structure from unparseable LLM text."""
    body_text = raw_text.strip() if raw_text else ""
    # Remove any markdown fences
    body_text = re.sub(r"```\s*(?:json|JSON)?\s*", "", body_text).strip()
    # Limit length
    if len(body_text) > 2000:
        body_text = body_text[:2000] + "..."

    return {
        "title": "Analysis Report",
        "subtitle": "Auto-generated from analysis data",
        "sections": [
            {
                "id": "the-read",
                "heading": "The read",
                "body": body_text if body_text else "Report generation encountered a formatting issue. Please review the tagged data directly.",
            }
        ],
        "findings": [],
        "evidence": [],
        "so_what": "Review the tagged data for detailed insights.",
    }


def _resolve_llm_for_report(session: dict, payload: GenerateReportPayload):
    """Determine the LLM provider/model to use for report generation.
    Priority: explicit payload > session's last run > env defaults.
    Returns (llm_instance, provider_name) or (None, None) if no key is available."""
    provider = payload.provider
    api_key = payload.api_key
    model = payload.model

    # If provider not explicitly given, try to infer from session's last run
    if not provider:
        # Check if a run was saved with provider info
        run_id = session.get("run_id")
        if run_id:
            run_file = RUNS_DIR / f"{run_id}.json"
            if run_file.exists():
                run_data = _read_json(run_file, {})
                provider = run_data.get("provider", "")
                if not model:
                    m = run_data.get("model", "")
                    if m and m != "default":
                        model = m

    # Try providers in order if none specified
    providers_to_try = []
    if provider:
        providers_to_try.append(provider)
    else:
        # Try each provider based on which env keys are set
        if os.getenv("ANTHROPIC_API_KEY"):
            providers_to_try.append("anthropic")
        if os.getenv("OPENAI_API_KEY"):
            providers_to_try.append("openai")
        if os.getenv("GROQ_API_KEY"):
            providers_to_try.append("groq")
        if os.getenv("GOOGLE_API_KEY"):
            providers_to_try.append("google")

    for prov in providers_to_try:
        try:
            llm = get_llm(prov, api_key, model)
            return llm, prov
        except Exception as e:
            log.warning(f"Could not initialize LLM provider '{prov}': {e}")
            continue

    return None, None


@app.post("/session/{session_id}/generate-report")
def generate_report(session_id: str, payload: GenerateReportPayload = None):
    """Generate a structured report from a session's analyzed (tagged) data.

    Uses the LLM to synthesize findings if a provider/key is available.
    Falls back to a statistical summary if no LLM is configured.
    """
    if payload is None:
        payload = GenerateReportPayload()

    session = get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])

    if not analyzed_data:
        raise HTTPException(
            status_code=400,
            detail="No analyzed data available. Run tagging first.",
        )

    # Check session status — warn if still running
    status = session.get("status", "unknown")
    if status == "running":
        log.info(f"Report generation requested for running session {session_id} — proceeding with partial data")

    log.info(f"Generating report for session {session_id} ({len(analyzed_data)} rows, status={status})")

    # Try to get an LLM
    llm, provider_name = _resolve_llm_for_report(session, payload)

    if llm is None:
        log.info(f"No LLM available for session {session_id} — generating statistical fallback report")
        report = _generate_fallback_report(session, analyzed_data)
        try:
            update_session(session_id, {"report": report})
            save_snapshot()
        except Exception as e:
            log.warning(f"Could not persist fallback report to session: {e}")
        return report

    # ── LLM-based report generation ───────────────────────────────────────
    log.info(f"Generating LLM report for session {session_id} via {provider_name}")

    context = session.get("dataset_context", {})
    report_type_id = session.get("report_type", DEFAULT_REPORT_TYPE_ID)
    stats = _collect_tag_stats(analyzed_data)
    stats_text = _build_stats_text(stats)
    sample_text = _build_sample_data(session, analyzed_data, max_samples=20)

    prompt_text = REPORT_GENERATION_PROMPT.format(
        filename=session.get("filename", "Dataset"),
        report_type=report_type_id,
        brand_focus=context.get("focus_brand", "Not specified"),
        dataset_type=context.get("dataset_type", "Not specified"),
        additional_context=context.get("additional_context", "None"),
        total_items=stats["total_rows"] - stats["error_rows"],
        tag_stats=stats_text,
        sample_data=sample_text,
    )

    try:
        response = llm.invoke(prompt_text)
        raw_content = response.content if hasattr(response, "content") else str(response)
        report = _parse_llm_report_json(raw_content)

        # If _parse_llm_report_json returned a minimal fallback (no findings),
        # and the raw text had content, try a retry with a stricter prompt
        if not report.get("findings") and len(raw_content) > 100:
            log.warning(f"First LLM call produced unparseable JSON for session {session_id}. Retrying with stricter prompt.")
            retry_prompt = REPORT_GENERATION_RETRY_PROMPT.format(
                filename=session.get("filename", "Dataset"),
                report_type=report_type_id,
                brand_focus=context.get("focus_brand", "Not specified"),
                total_items=stats["total_rows"] - stats["error_rows"],
                tag_stats=stats_text,
            )
            retry_response = llm.invoke(retry_prompt)
            retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
            retry_report = _parse_llm_report_json(retry_content)
            # Use the retry result only if it has actual findings
            if retry_report.get("findings"):
                report = retry_report
                log.info(f"Retry succeeded for session {session_id}")
            else:
                log.warning(f"Retry also failed to produce findings for session {session_id}")

    except Exception as e:
        log.error(f"LLM report generation failed for session {session_id}: {e}\n{traceback.format_exc()}")

        # Retry once with stricter prompt
        try:
            log.info(f"Retrying report generation with stricter prompt for session {session_id}")
            retry_prompt = REPORT_GENERATION_RETRY_PROMPT.format(
                filename=session.get("filename", "Dataset"),
                report_type=report_type_id,
                brand_focus=context.get("focus_brand", "Not specified"),
                total_items=stats["total_rows"] - stats["error_rows"],
                tag_stats=stats_text,
            )
            retry_response = llm.invoke(retry_prompt)
            retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
            report = _parse_llm_report_json(retry_content)
            log.info(f"Retry succeeded for session {session_id}")
        except Exception as retry_e:
            log.error(f"Retry also failed for session {session_id}: {retry_e}")
            log.info("Falling back to statistical report")
            report = _generate_fallback_report(session, analyzed_data)
            report["metadata"]["method"] = "statistical_fallback_after_llm_error"
            report["metadata"]["llm_error"] = str(e)[:300]
            return report

    # ── Validate and normalize the LLM response ──────────────────────────
    valid = stats["total_rows"] - stats["error_rows"]

    # Ensure required top-level keys exist with sensible defaults
    if "title" not in report or not report["title"]:
        focus = context.get("focus_brand", "")
        report["title"] = f"{focus or session.get('filename', 'Dataset')} — Analysis Report"
    if "subtitle" not in report or not report["subtitle"]:
        report["subtitle"] = f"Analysis of {valid} items"
    if "metadata" not in report:
        report["metadata"] = {}
    report["metadata"].setdefault("period", context.get("additional_context", "Not specified"))
    report["metadata"]["items_reviewed"] = valid
    report["metadata"]["report_type"] = report_type_id
    report["metadata"]["generated_at"] = datetime.utcnow().isoformat()
    report["metadata"]["method"] = "llm"
    report["metadata"]["provider"] = provider_name

    if "sections" not in report or not isinstance(report.get("sections"), list):
        report["sections"] = []
    if "findings" not in report or not isinstance(report.get("findings"), list):
        report["findings"] = []
    if "evidence" not in report or not isinstance(report.get("evidence"), list):
        report["evidence"] = []
    if "so_what" not in report or not report["so_what"]:
        report["so_what"] = "Review the findings above and take action based on the data."

    # Normalize findings
    for i, finding in enumerate(report["findings"]):
        finding.setdefault("number", i + 1)
        finding.setdefault("confidence", "medium")
        finding.setdefault("claim", "")
        finding.setdefault("support", "")
        # Validate confidence value
        if finding["confidence"] not in ("high", "medium", "low"):
            finding["confidence"] = "medium"

    # Normalize evidence
    for ev in report["evidence"]:
        ev.setdefault("source", session.get("filename", "Dataset"))
        ev.setdefault("quote", "")
        ev.setdefault("tags", [])
        ev.setdefault("sentiment", "unknown")
        if isinstance(ev["tags"], str):
            ev["tags"] = [t.strip() for t in ev["tags"].split(",") if t.strip()]

    log.info(f"LLM report generated for session {session_id}: "
             f"{len(report['sections'])} sections, {len(report['findings'])} findings, "
             f"{len(report['evidence'])} evidence items")

    try:
        update_session(session_id, {"report": report})
        save_snapshot()
    except Exception as e:
        log.warning(f"Could not persist LLM report to session: {e}")

    return report


# ═══════════════════════════════════════════════════════════════════════════════
#  REPORT REFINEMENT
# ═══════════════════════════════════════════════════════════════════════════════

REFINE_REPORT_PROMPT = """You are a senior insights analyst. You have been given an existing report and user feedback requesting changes.

Your task is to regenerate the report incorporating the user's feedback while preserving the data-backed nature of the original.

=== CURRENT REPORT ===
{current_report_json}

=== USER FEEDBACK ===
{feedback}

=== DESIGN THEME ===
{design_theme}

=== INSTRUCTIONS ===
Regenerate the report incorporating the user's feedback. If a design theme other than "default" is specified, adjust the tone and language to match (e.g., "corporate_blue" = formal/professional, "pharma_green" = clinical/precise, "bold_pink" = energetic/bold).

Return ONLY valid JSON in the exact same structure as the current report:
{{
  "title": "...",
  "subtitle": "...",
  "metadata": {{...}},
  "sections": [...],
  "findings": [...],
  "evidence": [...],
  "so_what": "..."
}}

=== RULES ===
1. Preserve the overall structure (sections, findings, evidence format).
2. Apply the user's feedback precisely — if they ask to sharpen findings, make them sharper. If they ask about tone, adjust it.
3. Keep all data/statistics accurate — do NOT invent numbers that weren't in the original.
4. Evidence quotes must remain verbatim from the original — do NOT fabricate quotes.
5. The metadata should be preserved but update "generated_at" to now and set "method" to "refined".
6. Return ONLY valid JSON. No preamble, no markdown fences, no text outside the JSON object.
"""


class RefineReportPayload(BaseModel):
    feedback: str
    design_theme: str = "default"


@app.post("/session/{session_id}/refine-report")
def refine_report(session_id: str, payload: RefineReportPayload):
    """Refine an existing report based on user feedback.

    Calls the LLM with the current report + feedback to regenerate.
    Falls back gracefully if no LLM key is available.
    """
    session = get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])

    if not analyzed_data:
        raise HTTPException(
            status_code=400,
            detail="No analyzed data available. Run tagging first.",
        )

    # Generate the current report to use as base for refinement
    current_report = None
    try:
        current_report = generate_report(session_id, GenerateReportPayload())
    except Exception as e:
        log.warning(f"Could not generate base report for refinement: {e}")
        current_report = _generate_fallback_report(session, analyzed_data)

    # Try to get an LLM for refinement
    llm, provider_name = _resolve_llm_for_report(session, GenerateReportPayload())

    if llm is None:
        log.info(f"No LLM available for session {session_id} — returning original report unchanged")
        if isinstance(current_report, dict):
            current_report.setdefault("metadata", {})
            current_report["metadata"]["refine_note"] = "No LLM API key configured — report unchanged"
        return current_report

    # Persist the design theme to the session for export
    if payload.design_theme and payload.design_theme != "default":
        update_session(session_id, {"design_theme": payload.design_theme})

    log.info(f"Refining report for session {session_id} via {provider_name}: feedback={payload.feedback[:100]}...")

    current_report_json = json.dumps(current_report, indent=2, default=str)

    prompt_text = REFINE_REPORT_PROMPT.format(
        current_report_json=current_report_json,
        feedback=payload.feedback,
        design_theme=payload.design_theme,
    )

    try:
        response = llm.invoke(prompt_text)
        raw_content = response.content if hasattr(response, "content") else str(response)
        refined_report = _parse_llm_report_json(raw_content)
    except Exception as e:
        log.error(f"LLM refinement failed for session {session_id}: {e}\n{traceback.format_exc()}")
        if isinstance(current_report, dict):
            current_report.setdefault("metadata", {})
            current_report["metadata"]["refine_error"] = str(e)[:300]
        return current_report

    # Normalize the refined report
    if "title" not in refined_report or not refined_report["title"]:
        refined_report["title"] = current_report.get("title", "Report")
    if "subtitle" not in refined_report or not refined_report["subtitle"]:
        refined_report["subtitle"] = current_report.get("subtitle", "")
    if "metadata" not in refined_report:
        refined_report["metadata"] = {}

    original_meta = current_report.get("metadata", {})
    refined_report["metadata"].setdefault("period", original_meta.get("period", ""))
    refined_report["metadata"].setdefault("items_reviewed", original_meta.get("items_reviewed", 0))
    refined_report["metadata"].setdefault("report_type", original_meta.get("report_type", ""))
    refined_report["metadata"]["generated_at"] = datetime.utcnow().isoformat()
    refined_report["metadata"]["method"] = "refined"
    refined_report["metadata"]["provider"] = provider_name
    refined_report["metadata"]["design_theme"] = payload.design_theme

    if "sections" not in refined_report or not isinstance(refined_report.get("sections"), list):
        refined_report["sections"] = current_report.get("sections", [])
    if "findings" not in refined_report or not isinstance(refined_report.get("findings"), list):
        refined_report["findings"] = current_report.get("findings", [])
    if "evidence" not in refined_report or not isinstance(refined_report.get("evidence"), list):
        refined_report["evidence"] = current_report.get("evidence", [])
    if "so_what" not in refined_report or not refined_report["so_what"]:
        refined_report["so_what"] = current_report.get("so_what", "")

    for i, finding in enumerate(refined_report["findings"]):
        finding.setdefault("number", i + 1)
        finding.setdefault("confidence", "medium")
        finding.setdefault("claim", "")
        finding.setdefault("support", "")
        if finding["confidence"] not in ("high", "medium", "low"):
            finding["confidence"] = "medium"

    for ev in refined_report["evidence"]:
        ev.setdefault("source", session.get("filename", "Dataset"))
        ev.setdefault("quote", "")
        ev.setdefault("tags", [])
        ev.setdefault("sentiment", "unknown")
        if isinstance(ev["tags"], str):
            ev["tags"] = [t.strip() for t in ev["tags"].split(",") if t.strip()]

    log.info(f"Report refined for session {session_id}: "
             f"{len(refined_report['sections'])} sections, {len(refined_report['findings'])} findings")

    return refined_report


# ═══════════════════════════════════════════════════════════════════════════════
#  HTML REPORT EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/session/{session_id}/export/html-report")
async def export_html_report(session_id: str):
    session = get_session(session_id)
    analyzed_data = session.get("analyzed_data", [])
    if not analyzed_data:
        raise HTTPException(status_code=400, detail="No analyzed data")

    from html_report_builder import build_pharma_html_report

    metadata = {
        "filename": session.get("filename", "Report"),
        "report_type": session.get("report_type", "pharma_social_intelligence"),
        "context": session.get("dataset_context", {}),
    }

    html = build_pharma_html_report(analyzed_data, metadata)

    # Apply design theme if one was set during refinement
    design_theme = session.get("design_theme", "default")
    if design_theme and design_theme != "default":
        connector = get_design_connector()
        html = connector.adjust_color_theme(html, design_theme)

    fname = session.get("filename", "report").rsplit(".", 1)[0]
    return StreamingResponse(
        iter([html.encode("utf-8")]),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{fname}_report.html"'}
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SKILL REGISTRY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

from skill_registry import get_skill_registry
from template_library import get_template_library
from methodology import get_methodology, get_methodology_steps, get_methodology_for_orchestrator
from skill_memory import save_run_as_skill, get_learned_preferences
from design_connector import get_design_connector
from mcp_registry import get_mcp_registry


class SkillUploadPayload(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    trigger_words: List[str] = []
    type: str = "uploaded"


class SkillMatchPayload(BaseModel):
    prompt: str


@app.get("/skills")
def api_list_skills():
    registry = get_skill_registry()
    return {"skills": registry.list_skills()}


@app.get("/skills/{skill_id}")
def api_get_skill(skill_id: str):
    registry = get_skill_registry()
    try:
        return registry.get_skill(skill_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/skills/upload")
def api_upload_skill(payload: SkillUploadPayload):
    registry = get_skill_registry()
    try:
        skill = registry.upload_skill(payload.model_dump(exclude_none=True))
        return {"ok": True, "skill": skill}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/skills/{skill_id}")
def api_delete_skill(skill_id: str):
    registry = get_skill_registry()
    try:
        deleted = registry.delete_skill(skill_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
        return {"ok": True, "deleted": skill_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/skills/match")
def api_match_skills(payload: SkillMatchPayload):
    registry = get_skill_registry()
    matched = registry.match_skill(payload.prompt)
    return {"matches": matched}


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMPLATE LIBRARY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateUploadPayload(BaseModel):
    name: str
    html_content: str
    description: str = ""
    report_types: List[str] = []
    tags: List[str] = []


@app.get("/templates")
def api_list_templates():
    library = get_template_library()
    return {"templates": library.list_templates()}


@app.get("/templates/{template_id}")
def api_get_template(template_id: str):
    library = get_template_library()
    try:
        return library.get_template(template_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/templates/upload")
def api_upload_template(payload: TemplateUploadPayload):
    library = get_template_library()
    try:
        meta = library.upload_template(
            name=payload.name,
            html_content=payload.html_content,
            metadata={
                "description": payload.description,
                "report_types": payload.report_types,
                "tags": payload.tags,
            },
        )
        return {"ok": True, "template": meta}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  METHODOLOGY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/methodology")
def api_get_methodology():
    return get_methodology()


@app.get("/methodology/steps")
def api_get_methodology_steps():
    return {"steps": get_methodology_steps()}


# ═══════════════════════════════════════════════════════════════════════════════
#  SKILL MEMORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class LearnFromRunPayload(BaseModel):
    session_id: str


@app.post("/skills/learn-from-run")
def api_learn_from_run(payload: LearnFromRunPayload):
    """After a successful run, extract configuration and save as a reusable skill."""
    session = get_session(payload.session_id)

    run_metadata = {
        "status": session.get("status", ""),
        "report_type": session.get("report_type", ""),
        "context": session.get("dataset_context", {}),
        "custom_schema": session.get("custom_schema"),
        "provider": session.get("provider", ""),
        "columns": session.get("columns", []),
        "schema_config": session.get("schema_config", {}),
    }

    result = save_run_as_skill(payload.session_id, run_metadata)
    if result:
        return {"ok": True, "learned": True, "skill": result}
    return {"ok": True, "learned": False, "message": "Run was not novel enough to save as a skill"}


@app.get("/skills/learned-preferences")
def api_get_learned_preferences():
    """Return accumulated preferences from past runs."""
    return get_learned_preferences()


# ═══════════════════════════════════════════════════════════════════════════════
#  DESIGN CONNECTOR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class ApplyThemePayload(BaseModel):
    html_content: str
    theme: str = "corporate_blue"
    brand_config: Optional[dict] = None


@app.get("/design/tools")
def api_list_design_tools():
    """List available design tools and their capabilities."""
    connector = get_design_connector()
    return {"tools": connector.list_tools()}


@app.post("/design/apply-theme")
def api_apply_design_theme(payload: ApplyThemePayload):
    """Apply a brand theme to HTML content."""
    connector = get_design_connector()

    html = payload.html_content

    if payload.brand_config:
        html = connector.apply_brand_theme(html, payload.brand_config)
    elif payload.theme and payload.theme != "default":
        html = connector.adjust_color_theme(html, payload.theme)

    return {"ok": True, "html_content": html}


# ═══════════════════════════════════════════════════════════════════════════════
#  MCP CONNECTOR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class MCPEnablePayload(BaseModel):
    config: dict = {}


@app.get("/mcp/connectors")
def api_list_mcp_connectors():
    """List all MCP connectors with their enabled/config status."""
    registry = get_mcp_registry()
    return {"connectors": registry.list_connectors()}


@app.get("/mcp/connectors/{connector_id}")
def api_get_mcp_connector(connector_id: str):
    """Get a specific MCP connector."""
    registry = get_mcp_registry()
    try:
        return registry.get_connector(connector_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/mcp/connectors/{connector_id}/enable")
def api_enable_mcp_connector(connector_id: str, payload: MCPEnablePayload):
    """Enable an MCP connector with the provided configuration."""
    registry = get_mcp_registry()
    try:
        connector = registry.enable_connector(connector_id, payload.config)
        return {"ok": True, "connector": connector}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/mcp/connectors/{connector_id}/disable")
def api_disable_mcp_connector(connector_id: str):
    """Disable an MCP connector."""
    registry = get_mcp_registry()
    try:
        connector = registry.disable_connector(connector_id)
        return {"ok": True, "connector": connector}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/mcp/connectors/{connector_id}/test")
def api_test_mcp_connector(connector_id: str):
    """Test an MCP connector's credentials."""
    registry = get_mcp_registry()
    try:
        return registry.test_connector(connector_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/mcp/active")
def api_list_active_mcp_connectors():
    """List only active (enabled) MCP connectors."""
    registry = get_mcp_registry()
    return {"connectors": registry.get_active_connectors()}


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSIONS — LIST / LOAD / DELETE / SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/sessions")
def api_list_sessions():
    """Return lightweight metadata for every known session.

    Intentionally omits the heavy fields (raw_data, analyzed_data, report) so
    a dashboard can list hundreds of sessions cheaply. Call /sessions/{sid}/load
    or /session/{sid} when you actually need the rows.
    """
    db = load_db()
    items = []
    for sid, s in db.get("sessions", {}).items():
        items.append({
            "session_id": sid,
            "filename": s.get("filename"),
            "status": s.get("status", "unknown"),
            "report_type": s.get("report_type"),
            "focus_brand": s.get("dataset_context", {}).get("focus_brand", ""),
            "row_count": len(s.get("raw_data", [])),
            "analyzed_count": len(s.get("analyzed_data", [])),
            "has_report": bool(s.get("report")),
            "is_demo": bool(s.get("is_demo")),
            "demo_id": s.get("demo_id"),
            "created_at": s.get("created_at"),
            "updated_at": s.get("updated_at") or s.get("created_at"),
            "run_id": s.get("run_id"),
        })
    # Most-recent first (best-effort — sort by updated_at, fall back to created_at)
    items.sort(key=lambda x: (x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return {"sessions": items, "count": len(items)}


@app.get("/sessions/{session_id}/load")
def api_load_session(session_id: str):
    """Load a full session payload (raw_data, analyzed_data, report) into the response.

    This is the explicit 'restore into the UI' endpoint — mirrors GET /session/{sid}
    but signals intent (and is the natural complement to DELETE /sessions/{sid}).
    """
    return get_session(session_id)


@app.delete("/sessions/{session_id}")
def api_delete_session(session_id: str):
    """Purge a session from the DB. Also removes any run files this session owns."""
    db = load_db()
    if session_id not in db.get("sessions", {}):
        raise HTTPException(status_code=404, detail="Session not found")

    removed_run_id = db["sessions"][session_id].get("run_id")
    del db["sessions"][session_id]
    save_db(db)

    # Also drop the corresponding run file + index entry if present
    if removed_run_id:
        try:
            run_file = RUNS_DIR / f"{removed_run_id}.json"
            if run_file.exists():
                run_file.unlink()
        except OSError as e:
            log.warning(f"Could not delete run file for {removed_run_id}: {e}")

        try:
            runs = load_runs()
            runs["runs"] = [r for r in runs.get("runs", []) if r.get("run_id") != removed_run_id]
            save_runs(runs)
        except Exception as e:
            log.warning(f"Could not prune runs index for {removed_run_id}: {e}")

    save_snapshot()
    log.info(f"Session deleted: {session_id} (run_id={removed_run_id})")
    return {"ok": True, "deleted": session_id}


@app.post("/sessions/snapshot")
def api_trigger_snapshot():
    """Manually trigger a snapshot save. Useful before a known-risky deploy."""
    path = save_snapshot()
    status = _ds_snapshot_status(DATA_DIR)
    return {"ok": path is not None, "snapshot": status}


# ═══════════════════════════════════════════════════════════════════════════════
#  DEMO RUNS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/demos")
def api_list_demos():
    """List available pre-baked demo runs."""
    return {"demos": list_demos()}


@app.post("/demos/{demo_id}/load")
def api_load_demo(demo_id: str):
    """Materialize a demo run into a NEW session for the current user.

    A fresh session_id is minted so the demo template stays pristine and
    multiple users / loads don't interfere with each other.
    """
    if get_demo(demo_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown demo: {demo_id}")

    new_session_id = str(uuid.uuid4())
    session_payload = build_demo_session(demo_id, new_session_id)
    if session_payload is None:
        raise HTTPException(status_code=500, detail="Failed to build demo session")

    db = load_db()
    db.setdefault("sessions", {})
    db["sessions"][new_session_id] = session_payload
    save_db(db)
    save_snapshot()

    log.info(f"Demo loaded: {demo_id} -> session={new_session_id}")
    return {
        "ok": True,
        "session_id": new_session_id,
        "demo_id": demo_id,
        "title": session_payload.get("demo_title"),
        "filename": session_payload.get("filename"),
        "row_count": session_payload.get("row_count"),
        "status": session_payload.get("status"),
        "has_report": bool(session_payload.get("report")),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  AGENTIC ORCHESTRATOR ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from orchestrator_endpoint import router as orchestrator_router
    app.include_router(orchestrator_router)
    log.info("Orchestrator endpoint registered.")
except Exception as e:
    log.warning(f"Orchestrator not available: {e}")
