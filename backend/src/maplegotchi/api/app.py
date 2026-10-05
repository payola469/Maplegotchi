"""The FastAPI application: read endpoints, Greet/Pet, SSE, and the static frontend.

Routes are thin: every one calls MapleService, which calls the single-writer
LifeRuntime. There is no generic action endpoint, no free-text input, and no
admin/debug surface in production (API docs exist only in development).
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from maplegotchi.api import views
from maplegotchi.api.models import (
    DecisionOut,
    HealthOut,
    InteractionOut,
    JournalEntryOut,
    LifeEventsOut,
    MapleOut,
    ObservationOut,
    RoomOut,
    ServerOut,
    SnapshotOut,
    StatusOut,
    TimelineEventOut,
)
from maplegotchi.api.security import (
    BodyLimitMiddleware,
    SecurityHeadersMiddleware,
    origin_guard,
    require_empty_body,
)
from maplegotchi.api.static import install_frontend
from maplegotchi.api.stream import event_stream
from maplegotchi.config import Settings
from maplegotchi.core.interactions import Rejected
from maplegotchi.core.state import InteractionKind
from maplegotchi.runtime.life import LifeRecords, RuntimeClosedError
from maplegotchi.runtime.service import MapleService
from maplegotchi.storage.errors import StorageError

MAX_RECENT = 100
MAX_LIFE_EVENTS = 500


def _complete_cutoff(records: LifeRecords, limit: int) -> int | None:
    """The first revision that may be incomplete, or None if every store was read fully.

    Each store is read with its own `limit`; a store that hit it may stop part-way
    through a revision, and the other stores may already include later revisions.
    """
    capped = [
        max(row.revision for row in rows)
        for rows in (records.timeline, records.actions, records.decisions)
        if len(rows) >= limit
    ]
    return min(capped) if capped else None


def create_app(
    service: MapleService,
    settings: Settings,
    *,
    run_life_loop: bool = True,
    sse_max_events: int | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if run_life_loop:
            service.start_life_loop(settings.loop_poll_seconds)
        try:
            yield
        finally:
            if run_life_loop:
                await service.stop_life_loop()

    docs = settings.docs_enabled
    app = FastAPI(
        title="Maplegotchi",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(RuntimeClosedError)
    async def closed(request: Request, exc: RuntimeClosedError) -> JSONResponse:
        return JSONResponse({"detail": "Maple is not running"}, status_code=503)

    @app.exception_handler(StorageError)
    async def storage_failed(request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse({"detail": "Maple's storage is unavailable"}, status_code=503)

    api = APIRouter(prefix="/api")
    trusted_origin = origin_guard(settings.allowed_origins)

    @api.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(status="ok")

    @api.get("/snapshot", response_model=SnapshotOut)
    def snapshot() -> SnapshotOut:
        return views.snapshot(service.snapshot())

    @api.get("/maple", response_model=MapleOut)
    def maple() -> MapleOut:
        return views.maple(service.snapshot(recent=0))

    @api.get("/decisions", response_model=list[DecisionOut])
    def decisions(limit: int = Query(20, ge=1, le=MAX_RECENT)) -> list[DecisionOut]:
        """The decision audit, most recent `limit`, oldest first (ADR-0026 §8)."""
        return [views.decision(d) for d in service.runtime.decisions(limit=limit)]

    @api.get("/life-events", response_model=LifeEventsOut)
    def life_events(
        after_revision: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=MAX_LIFE_EVENTS),
    ) -> LifeEventsOut:
        """Life events committed after `after_revision` (a cursor for any client)."""
        records = service.runtime.life_since(after_revision, limit=limit)
        events = views.life_events(records)
        # Only whole revisions are returned, so a client never misses part of one.
        cutoff = _complete_cutoff(records, limit)
        if cutoff is not None:
            events = [e for e in events if e.revision < cutoff]
            if not events:  # one revision holds more than `limit`: serve it whole
                events = views.life_events(service.runtime.life_written_at(cutoff))
        last = events[-1].revision if events else after_revision
        return LifeEventsOut(events=events, last_revision=last)

    @api.get("/room", response_model=RoomOut)
    def room() -> RoomOut:
        return views.room()

    @api.get("/status", response_model=StatusOut)
    def status() -> StatusOut:
        return views.status(service.snapshot(recent=0))

    @api.get("/observations/latest", response_model=list[ObservationOut])
    def latest_observations() -> list[ObservationOut]:
        return [views.observation(o) for o in service.runtime.latest_observations()]

    @api.get("/server", response_model=ServerOut)
    def server() -> ServerOut:
        return views.server(service.snapshot(recent=0))

    @api.get("/journal", response_model=list[JournalEntryOut])
    def journal(limit: int = Query(20, ge=1, le=MAX_RECENT)) -> list[JournalEntryOut]:
        return [views.journal_entry(e) for e in service.runtime.journal(limit=limit)]

    @api.get("/timeline", response_model=list[TimelineEventOut])
    def timeline(limit: int = Query(20, ge=1, le=MAX_RECENT)) -> list[TimelineEventOut]:
        return [views.timeline_event(e) for e in service.runtime.timeline(limit=limit)]

    def interact(kind: InteractionKind) -> JSONResponse:
        result = service.interact(kind)
        body = views.interaction(result, kind.value)
        if isinstance(result.outcome, Rejected):
            retry = max(1, math.ceil(result.outcome.retry_after.total_seconds()))
            return JSONResponse(
                body.model_dump(mode="json"), status_code=429, headers={"retry-after": str(retry)}
            )
        return JSONResponse(body.model_dump(mode="json"), status_code=200)

    interaction_responses: dict[int | str, dict[str, object]] = {
        429: {"model": InteractionOut, "description": "rejected by cooldown or rate limit"},
        403: {"description": "untrusted Origin"},
    }

    @api.post(
        "/interactions/greet",
        response_model=InteractionOut,
        responses=interaction_responses,
        dependencies=[Depends(trusted_origin), Depends(require_empty_body)],
    )
    def greet() -> JSONResponse:
        return interact(InteractionKind.GREET)

    @api.post(
        "/interactions/pet",
        response_model=InteractionOut,
        responses=interaction_responses,
        dependencies=[Depends(trusted_origin), Depends(require_empty_body)],
    )
    def pet() -> JSONResponse:
        return interact(InteractionKind.PET)

    @api.get("/events", response_class=StreamingResponse)
    async def events(request: Request) -> StreamingResponse:
        stream = event_stream(
            service,
            request.headers.get("last-event-id"),
            request.is_disconnected,
            max_events=sse_max_events,
        )
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={"cache-control": "no-store", "x-accel-buffering": "no"},
        )

    app.include_router(api)
    # Unknown /api/* paths get FastAPI's JSON 404; the frontend fallback refuses them too.
    if settings.static_dir is not None:
        install_frontend(app, settings.static_dir)
    return app
