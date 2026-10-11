"""Additive GET surface; normal app has no mechanism to inject fixture truth."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from maplegotchi.api.world_models import (
    WorldCatalogOut,
    WorldOut,
    WorldPlacementsOut,
    WorldUnavailableOut,
)


def unavailable_world_router() -> APIRouter:
    router = APIRouter(prefix="/api/world", tags=["world"])
    unavailable: dict[int | str, dict[str, object]] = {
        503: {"model": WorldUnavailableOut, "description": "No live canonical world"}
    }

    def response() -> JSONResponse:
        return JSONResponse(WorldUnavailableOut().model_dump(mode="json"), status_code=503)

    router.add_api_route(
        "",
        response,
        methods=["GET"],
        response_model=WorldOut,
        responses=unavailable,
        operation_id="read_world",
    )
    router.add_api_route(
        "/catalog",
        response,
        methods=["GET"],
        response_model=WorldCatalogOut,
        responses=unavailable,
        operation_id="read_world_catalog",
    )
    router.add_api_route(
        "/placements",
        response,
        methods=["GET"],
        response_model=WorldPlacementsOut,
        responses=unavailable,
        operation_id="read_world_placements",
    )
    return router
