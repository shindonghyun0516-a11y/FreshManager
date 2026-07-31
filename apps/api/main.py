from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.schemas import ErrorDetail, ErrorResponse, HealthResponse

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
