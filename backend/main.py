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

# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

LOG_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).parent))) / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
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
#  PYDANTIC OUTPUT SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class XAIRationale(BaseModel):
    text_evidence: str = Field(
        description="EXACT verbatim quote(s) from the source text. Must be a direct copy-paste."
    )
    theme_reasoning: str = Field(
        description="Step-by-step explanation of why this theme was chosen, referencing text_evidence."
    )
    sentiment_reasoning: str = Field(
        description="Why this sentiment label was assigned — be nuanced (aspirational, cautionary, etc.)."
    )
    signal_reasoning: str = Field(
        description="Why these signals were flagged — what PR risk or opportunity do they represent?"
    )
    confidence_reasoning: str = Field(
        description="Why this confidence score was assigned. What ambiguity or clarity affected it?"
    )

class RowAnalysis(BaseModel):
    brand: str = Field(description="The primary brand this text is focused on. Empty string if it's a general industry text.")
    sub_brands: List[str] = Field(description="List of specific products, services, or sub-brands belonging to the primary brand. Do not list independent companies here.")
    entities: List[str] = Field(description="List of all Named Entities: Companies, Organizations, People, and Locations mentioned in the text.")
    theme: str = Field(description="Primary theme. One of: Brand Reputation, Crisis & Risk, Product/Service, Leadership & Governance, ESG & Sustainability, Financial Performance, Innovation & Technology, Competitive Landscape, Community & Culture, Regulatory & Legal, Customer Experience, Employee Relations")
    sub_theme_1: str = Field(description="First sub-theme — more specific categorisation within primary theme")
    sub_theme_2: str = Field(description="Second sub-theme or empty string if not applicable")
    sub_theme_3: str = Field(description="Third sub-theme or empty string if not applicable")
    sentiment: str = Field(description="Sentiment label: Positive / Negative / Neutral / Mixed")
    sentiment_nuance: str = Field(description="Nuanced descriptor: Aspirational, Cautionary, Inflammatory, Celebratory, Investigative, Sceptical, Empathetic, Urgent, Satirical, Factual")
    emotion: str = Field(description="Dominant emotion: Joy, Trust, Anticipation, Surprise, Fear, Anger, Disgust, Sadness, or Neutral")
    driver: str = Field(description="The specific factor or actor driving the narrative (e.g. CEO statement, product recall, earnings miss)")
    severity: int = Field(description="Reputational severity 1-10. 1=benign/positive, 5=moderate, 10=crisis. Positive content: 1-3.", ge=1, le=10)
    signals: str = Field(description="Comma-separated PR signals. Options: Crisis Signal, Viral Potential, Influencer Mention, Regulatory Scrutiny, Competitive Threat, Brand Advocacy, Earned Media, Negative Earned Media, Executive Spotlight, Policy Impact, Consumer Backlash, ESG Alert, Misinformation Risk")
    confidence: float = Field(description="Confidence 0.0-1.0. Short/ambiguous text → lower. Clear explicit statements → higher.", ge=0.0, le=1.0)
    xai_rationale: XAIRationale = Field(description="Detailed XAI rationale proving every decision is grounded in source text")

# ═══════════════════════════════════════════════════════════════════════════════
#  PR ANALYST SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

PR_SYSTEM_PROMPT = """You are ARIA — Advanced Reputation Intelligence Analyst — a world-class PR and Media Intelligence specialist with 20 years of experience advising Fortune 500 brands, government bodies, and NGOs on reputation management.

Analyse this media content (social post, article, review, press release) and produce a structured intelligence report.

=== ANALYTICAL FRAMEWORK ===
1. BRAND: Identify the primary brand this text is about (if any). If it's a general industry text, leave empty.
2. SUB-BRANDS: List specific products, services, or sub-brands belonging to the primary brand. Do NOT list independent companies here.
3. ENTITIES: Extract a list of ALL distinct Named Entities (Organizations, Companies, People, Locations). Ensure all companies mentioned are captured here.
4. THEME: Map to ONE primary theme from the taxonomy.
5. SUB-THEMES: Up to 3, each more specific than the parent. Do NOT repeat the parent.
6. SENTIMENT: Assign polarity (Positive/Negative/Neutral/Mixed) AND nuance (Aspirational, Cautionary, etc.)
7. EMOTION: The dominant emotion the AUTHOR projects — reveals media framing bias.
8. SEVERITY (1-10 reputational impact):
   1-2: Positive brand building · 3-4: Low risk · 5-6: Monitor · 7-8: Respond · 9-10: Crisis
9. SIGNALS: Early-warning flags. Only flag signals CLEARLY evidenced in text.
10. CONFIDENCE: Be calibrated. Short/ambiguous → <0.7. Clear detailed text → >0.85.

=== ANTI-HALLUCINATION RULES ===
- xai_rationale.text_evidence MUST be verbatim copy from the SOURCE TEXT. Never paraphrase.
- Do NOT infer facts not present in the source text.
- If ambiguous, lower the confidence score.
- Never fabricate sub-themes, signals, or drivers not supported by quoted text.

=== CONTEXT ===
Brand Focus: {brand_focus}
Dataset Type: {dataset_type}
Additional Context: {additional_context}

=== SOURCE TEXT ===
{source_text}

=== OUTPUT FORMAT ===
{format_instructions}

Produce ONLY the JSON object. No preamble. No text outside the JSON."""

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

def analyse_row(llm, parser, prompt_template, row_text: str, context: dict, row_idx: int) -> dict:
    import time
    import random
    chain = prompt_template | llm | parser
    log.info(f"  Analysing row {row_idx}: {row_text[:80]}…")
    
    max_retries = 5
    base_delay = 5.0
    
    for attempt in range(max_retries):
        try:
            result: RowAnalysis = chain.invoke({
                "brand_focus":        context.get("focus_brand", "Not specified"),
                "dataset_type":       context.get("dataset_type", "Mixed / unknown"),
                "additional_context": context.get("additional_context", "None provided"),
                "source_text":        row_text,
                "format_instructions": parser.get_format_instructions(),
            })
            data = result.model_dump()
            xai  = data.pop("xai_rationale", {})
            data["xai_text_evidence"]       = xai.get("text_evidence", "")
            data["xai_theme_reasoning"]     = xai.get("theme_reasoning", "")
            data["xai_sentiment_reasoning"] = xai.get("sentiment_reasoning", "")
            data["xai_signal_reasoning"]    = xai.get("signal_reasoning", "")
            data["xai_confidence_reasoning"]= xai.get("confidence_reasoning", "")
            log.info(f"  Row {row_idx} → theme={data.get('theme')} sentiment={data.get('sentiment')} confidence={data.get('confidence')}")
            return data
        except OutputParserException as e:
            log.error(f"  Row {row_idx} parse error: {e}")
            raw = str(e)
            try:
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    out = {k: parsed.get(k, "") for k in ["brand", "theme","sub_theme_1","sub_theme_2","sub_theme_3",
                            "sentiment","sentiment_nuance","emotion","driver","signals"]}
                    out["sub_brands"] = parsed.get("sub_brands", [])
                    out["entities"] = parsed.get("entities", [])
                    out.update({"severity": int(parsed.get("severity",5)), "confidence": float(parsed.get("confidence",0.0)),
                                 "xai_text_evidence": "⚠ Parse fallback — partial extraction", "error": True})
                    return out
            except Exception:
                pass
            return {"brand":"", "sub_brands":[], "entities":[], "theme":"Parse Error","sub_theme_1":"","sub_theme_2":"","sub_theme_3":"",
                    "sentiment":"Unknown","sentiment_nuance":"","emotion":"","driver":"",
                    "severity":5,"signals":"","confidence":0.0,
                    "xai_text_evidence":f"⚠ Error: {str(e)[:300]}","error":True}
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate limit" in err_str or "quota" in err_str or "resource exhausted" in err_str:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    log.warning(f"  Row {row_idx} hit rate limit. Retrying in {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
            
            log.error(f"  Row {row_idx} unexpected error: {e}")
            return {"brand":"", "sub_brands":[], "entities":[], "theme":"Error","sub_theme_1":"","sub_theme_2":"","sub_theme_3":"",
                    "sentiment":"Unknown","sentiment_nuance":"","emotion":"","driver":"",
                    "severity":5,"signals":"","confidence":0.0,
                    "xai_text_evidence":f"⚠ Unexpected error: {str(e)[:300]}","error":True}

# ═══════════════════════════════════════════════════════════════════════════════
#  BATCH PROCESSING ENGINE
#  Strategy: concurrent batches of BATCH_SIZE rows, max MAX_WORKERS threads.
#  Good balance for LLM APIs: avoids rate limits, handles 1000-row files fine.
# ═══════════════════════════════════════════════════════════════════════════════

BATCH_SIZE  = int(os.getenv("BATCH_SIZE",  "5"))   # rows per concurrent batch
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))   # parallel threads per batch

def _run_tagging_bg(session_id: str, provider: str, api_key: str,
                    model: Optional[str], session: dict, run_id: str):
    start_time = datetime.utcnow()
    log.info(f"=== RUN {run_id} START | session={session_id} provider={provider} model={model} ===")

    try:
        llm    = get_llm(provider, api_key, model)
        parser = PydanticOutputParser(pydantic_object=RowAnalysis)
        prompt = PromptTemplate(
            template=PR_SYSTEM_PROMPT,
            input_variables=["brand_focus","dataset_type","additional_context","source_text"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        schema_cfg = session["schema_config"]
        text_col   = schema_cfg["primary_text_column"]
        context    = session.get("dataset_context", {})
        raw_data   = session["raw_data"]
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

        analyzed: List[dict] = [None] * total  # pre-allocate to preserve order

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
                
            ai_result = analyse_row(llm, parser, prompt, row_text, context, idx)
            return idx, {**row, **ai_result}

        # Process in batches to control concurrency
        completed = 0
        for batch_start in range(0, total, BATCH_SIZE * workers):
            batch_end  = min(batch_start + BATCH_SIZE * workers, total)
            batch_rows = [(i, raw_data[i]) for i in range(batch_start, batch_end)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(process_row, item): item[0] for item in batch_rows}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        idx, merged = fut.result()
                        analyzed[idx] = merged
                        completed += 1
                        progress = int(completed / total * 100)
                        # Save every row incrementally so frontend sees live updates
                        update_session(session_id, {
                            "analyzed_data": [r for r in analyzed if r is not None],
                            "progress": progress,
                            "status": "running",
                        })
                        log.info(f"Run {run_id}: {completed}/{total} ({progress}%)")
                    except Exception as e:
                        orig_idx = futures[fut]
                        log.error(f"Run {run_id}: row {orig_idx} worker exception: {e}")
                        analyzed[orig_idx] = {**raw_data[orig_idx],
                            "theme":"Worker Error","sentiment":"Unknown","confidence":0.0,
                            "xai_text_evidence":f"⚠ Worker error: {str(e)[:200]}","error":True}

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        final_data = [r for r in analyzed if r is not None]

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
            "total_rows":  total,
            "completed":   completed,
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
            "model": model or "default", "status": "error",
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

@app.post("/run-tagging")
def run_tagging(payload: RunTaggingPayload, background_tasks: BackgroundTasks):
    session = get_session(payload.session_id)
    if not session.get("schema_config", {}).get("primary_text_column"):
        raise HTTPException(status_code=400, detail="Schema not configured — set primary_text_column first")

    run_id = str(uuid.uuid4())[:8]
    log.info(f"Starting run {run_id} for session {payload.session_id}")
    update_session(payload.session_id, {
        "status": "running", "analyzed_data": [], "progress": 0, "run_id": run_id
    })
    background_tasks.add_task(
        _run_tagging_bg,
        payload.session_id, payload.provider, payload.api_key,
        payload.model, session, run_id,
    )
    return {"ok": True, "run_id": run_id, "message": "Tagging started"}


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
