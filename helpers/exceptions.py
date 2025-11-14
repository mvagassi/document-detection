from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from typing import Any, Optional


# ✅ Helper untuk response sukses / error konsisten
def json_response(
    status_code: int,
    message: str,
    data: Optional[Any] = None,
    success: bool = True,
    extra: Optional[dict] = None
):
    base_content = {
        "status": success,
        "data": data,
        "message": message,
    }

    # Gabungkan dengan field tambahan (jika ada)
    if extra:
        base_content.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=base_content,
    )


# ✅ 200 OK (misal untuk response sukses tanpa insert)
async def ok_response(request: Request, message: str = "Success", data=None):
    return json_response(HTTP_200_OK, message, data, True)


# ✅ 201 Created
async def created_response(request: Request, message: str = "Created successfully", data=None):
    return json_response(HTTP_201_CREATED, message, data, True)


# ✅ 400 Bad Request (misal input invalid)
async def value_error_handler(request: Request, exc: ValueError):
    return json_response(HTTP_400_BAD_REQUEST, str(exc), None, False)


# ✅ 401 Unauthorized (token invalid)
async def unauthorized_handler(request: Request, exc: Exception):
    return json_response(HTTP_401_UNAUTHORIZED, "Unauthorized access", None, False)


# ✅ 403 Forbidden (tidak punya izin)
async def forbidden_handler(request: Request, exc: Exception):
    return json_response(HTTP_403_FORBIDDEN, "Access forbidden", None, False)


# ✅ 404 Not Found (data tidak ditemukan)
async def not_found_handler(request: Request, exc: Exception):
    return json_response(HTTP_404_NOT_FOUND, "Resource not found", None, False)


# ✅ 422 Unprocessable Entity (error validasi body)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    return json_response(
        HTTP_422_UNPROCESSABLE_ENTITY,
        "Invalid request data",
        exc.errors(),
        False,
    )


# ✅ 500 Internal Server Error (error tidak terduga)
async def global_exception_handler(request: Request, exc: Exception):
    return json_response(
        HTTP_500_INTERNAL_SERVER_ERROR,
        f"Internal Server Error: {exc}",
        None,
        False,
    )