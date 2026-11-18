"""Consistent error envelope: {"error": {"code", "message", "details", "request_id"}}."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("ledgerflow.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: object | None = None, code: str | None = None,
                 status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class Unauthorized(AppError):
    status_code, code = 401, "unauthorized"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class BusinessRuleError(AppError):
    status_code, code = 422, "business_rule_violation"


class TooManyRequests(AppError):
    status_code, code = 429, "rate_limited"


def _body(request: Request, code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details,
                      "request_id": getattr(request.state, "request_id", None)}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        if exc.status_code >= 500:
            # Server-side failures are logged with internal detail; the client sees only the safe message.
            log.error("%s request_id=%s path=%s detail=%s", exc.code, getattr(request.state, "request_id", None),
                      request.url.path, getattr(exc, "log_detail", exc.message))
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(_body(request, "validation_error", "Request validation failed", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(request, "http_error", str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Full diagnostics go to logs; the client gets a safe message + request id.
        log.exception("Unhandled error request_id=%s path=%s", getattr(request.state, "request_id", None), request.url.path)
        return JSONResponse(_body(request, "internal_error", "An unexpected error occurred."), status_code=500)
