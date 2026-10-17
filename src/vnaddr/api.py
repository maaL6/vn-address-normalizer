"""FastAPI service.

Run:  uvicorn vnaddr.api:app --port 8000   (with PYTHONPATH=src)
"""
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints

from .pipeline import Normalizer

WEB = Path(__file__).resolve().parents[2] / "web" / "index.html"
MAX_BATCH = 1000

@lru_cache(maxsize=1)
def normalizer() -> Normalizer:
    return Normalizer()


@asynccontextmanager
async def lifespan(_app):
    normalizer().normalize("1 Lê Lợi, P. Bến Nghé, Q.1, TP.HCM")  # load + warm up the model once
    yield


app = FastAPI(title="Vietnamese address normalizer (2025 administrative reform)", version="1.0.0",
              lifespan=lifespan)


Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class One(BaseModel):
    address: Address = Field(..., examples=["12 ng trai p.ben thanh q1 tphcm"])


class Many(BaseModel):
    addresses: list[Address] = Field(..., min_length=1, max_length=MAX_BATCH)


@app.get("/health")
def health():
    n = normalizer()
    return {"status": "ok", "tagger": getattr(n.tagger, "name", "rules"), "gazetteer": n.gz.source}


@app.post("/normalize")
def normalize(req: One):
    t0 = time.perf_counter()
    out = normalizer().normalize(req.address)
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


@app.post("/normalize/batch")
def normalize_batch(req: Many):
    t0 = time.perf_counter()
    out = normalizer().normalize_batch(req.addresses)
    return {"results": out, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


@app.get("/")
def index():
    return FileResponse(WEB)
