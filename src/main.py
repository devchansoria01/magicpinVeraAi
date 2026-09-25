"""Vera engine FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from src.routes.context_route import router as context_router
from src.routes.reply_route import router as reply_router
from src.routes.tick_route import router as tick_router
from src.store import store

app = FastAPI(title="vera-engine", version="1.0.0")
app.include_router(context_router)
app.include_router(tick_router)
app.include_router(reply_router)


@app.get("/v1/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime_seconds": store.uptime_seconds(),
        "contexts_loaded": store.counts(),
    }


@app.get("/v1/metadata")
async def metadata():
    return {
        "name": "vera-engine",
        "team_name": "Vera Engine",
        "team_members": ["Raj"],
        "model": "deterministic-heuristic-v1",
        "approach": "versioned context store + trigger-kind dispatch compose() with grounded facts; no hallucinated numbers",
        "contact_email": "raj@example.com",
        "version": "1.0.0",
        "submitted_at": "2026-04-26T08:00:00Z",
    }


@app.post("/v1/teardown")
async def teardown():
    store.teardown()
    return {"ok": True}
