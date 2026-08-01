from typing import Annotated

from fastapi import FastAPI, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.schemas import (
    AreaPilotResponse,
    AreasResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
)

app = FastAPI(title="FreshManager API", version="0.1.0")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(
    _request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    if exception.status_code == 404:
        return _error_response(
            404,
            "NOT_FOUND",
            "요청한 API 경로를 찾을 수 없습니다.",
        )
    return _error_response(
        exception.status_code,
        "HTTP_ERROR",
        "요청을 처리할 수 없습니다.",
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _request: Request,
    _exception: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        422,
        "REQUEST_VALIDATION_FAILED",
        "요청 형식이 올바르지 않습니다.",
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(
    _request: Request,
    _exception: Exception,
) -> JSONResponse:
    return _error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "요청을 처리할 수 없습니다.",
    )


@app.get("/api/v1/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service="freshmanager-api")


def _pilot_service():
    service = getattr(app.state, "pilot_service", None)
    if service is None:
        from freshmanager.selected_area_pilot import SelectedAreaPilotService

        service = SelectedAreaPilotService()
        app.state.pilot_service = service
    return service


@app.get("/api/v1/areas", response_model=AreasResponse)
def get_areas() -> AreasResponse:
    return AreasResponse(areas=_pilot_service().list_areas(), selection_mode="USER_CHOICE")


@app.get("/api/v1/areas/{area_code}/pilot-view", response_model=AreaPilotResponse)
def get_area_pilot_view(
    area_code: Annotated[str, Path(pattern=r"^POI\d{3}$")],
) -> AreaPilotResponse | JSONResponse:
    from freshmanager.selected_area_pilot import SelectedAreaPilotError

    try:
        return AreaPilotResponse.model_validate(
            _pilot_service().get_pilot_view(area_code)
        )
    except SelectedAreaPilotError as error:
        code = str(error)
        if code == "AREA_NOT_SUPPORTED":
            return _error_response(404, code, "지원하지 않는 Area입니다.")
        if code == "SPOT_PROTOTYPE_CONTRACT_INVALID":
            return _error_response(
                500,
                code,
                "후보 위치 정보를 안전하게 제공할 수 없습니다.",
            )
        if code == "AREA_DATA_PROVIDER_UNAVAILABLE":
            return _error_response(
                503,
                code,
                "Area 데이터를 안전하게 제공할 수 없습니다.",
            )
        return _error_response(
            500,
            "INTERNAL_SERVER_ERROR",
            "요청을 처리할 수 없습니다.",
        )
