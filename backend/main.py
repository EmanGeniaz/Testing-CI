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

# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

_log_handlers = [logging.StreamHandler()]
try:
    LOG_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).parent))) / "app.log"
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

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH   = DATA_DIR / "database.json"
RUNS_PATH = DATA_DIR / "runs.json"
RUNS_DIR  = DATA_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)
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
        mdl = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
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
        log.info(f"=== RUN {run_id} COMPLETE | {completed}/{total} rows in {elapsed:.1f}s ===")

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


REPORT_GENERATION_PROMPT = """You are a senior insights analyst. You have been given a dataset of tagged media/social intelligence data that has already been analyzed with themes, sentiments, signals, drivers, and supporting evidence.

Your task is to synthesize this data into a structured executive report.

=== CONTEXT ===
Dataset: {filename}
Report Type: {report_type}
Brand/Focus: {brand_focus}
Dataset Type: {dataset_type}
Additional Context: {additional_context}
Total Items Analyzed: {total_items}

=== TAG STATISTICS ===
{tag_stats}

=== SAMPLE TAGGED DATA (representative rows) ===
{sample_data}

=== INSTRUCTIONS ===

Produce a JSON report with exactly this structure:

{{
  "title": "<Dataset/Brand name> — <key finding headline>",
  "subtitle": "One sentence summarizing the overall read of the data",
  "sections": [
    {{
      "id": "the-read",
      "heading": "The read",
      "body": "Executive summary paragraph. Use **bold** for key statistics and important terms. Reference the data — cite counts and percentages."
    }},
    {{
      "id": "<section-slug>",
      "heading": "<Section heading>",
      "body": "Analytical paragraph with data-backed insights. Use **bold** for emphasis."
    }}
  ],
  "findings": [
    {{
      "number": 1,
      "confidence": "high",
      "claim": "Key finding statement with *emphasis* on the core insight",
      "support": "Supporting evidence with specific numbers, percentages, and data citations from the analysis"
    }}
  ],
  "evidence": [
    {{
      "source": "Original data source/filename",
      "quote": "Verbatim text from the analyzed data",
      "tags": ["theme_tag", "signal_tag"],
      "sentiment": "positive"
    }}
  ],
  "so_what": "Actionable recommendations paragraph. Be specific and strategic."
}}

=== RULES ===
1. Produce 2-4 sections. The first section MUST have id="the-read" and be the executive summary.
2. Produce 3-5 findings ranked by frequency and strategic importance. Each must have confidence: "high", "medium", or "low".
3. Produce 3-10 evidence items. Quotes MUST be verbatim from the sample data provided — do NOT fabricate quotes.
4. The "so_what" should be actionable, strategic, and specific to the data.
5. Use **bold** for emphasis in section bodies and *italics* in finding claims.
6. Ground everything in the actual statistics and data provided. Do NOT invent numbers.
7. Return ONLY valid JSON. No preamble, no markdown fences, no text outside the JSON object.
"""


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


def _parse_llm_report_json(raw_text: str) -> dict:
    """Extract and parse JSON from the LLM response, handling markdown fences
    and other common LLM response quirks."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        candidate = text[brace_start:brace_end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse LLM response as JSON. Raw response (first 500 chars): {raw_text[:500]}")


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
    except Exception as e:
        log.error(f"LLM report generation failed for session {session_id}: {e}\n{traceback.format_exc()}")
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

    return report
