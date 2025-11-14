from fastapi import FastAPI
from core.config import settings
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from api.router import api_router
import os

version = "dev"  # default version

if os.path.exists("VERSION"):
    with open("VERSION") as f:
        version = f.read().strip()
else:
    # fallback: ambil dari git langsung jika ada git repo
    try:
        import subprocess
        version = subprocess.check_output(["git", "describe", "--tags"]).decode().strip()
    except Exception:
        version = "dev"  # kalau gagal tetap default

app = FastAPI(
    title="Document Detection",
    description="",
    version=version
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# @app.on_event("startup")
# async def startup_event():
#     # ✅ Cek koneksi pertama kali (warm up)
#     async with engine.begin() as conn:
#         await conn.run_sync(lambda _: None)
#     print("✅ Database connected and engine initialized.")

# @app.on_event("shutdown")
# async def shutdown_event():
#     # ✅ Tutup engine SQLAlchemy
#     await engine.dispose()
#     print("✅ Database engine disposed.")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []
    for error in exc.errors():
        field = error.get("loc")[-1]  # Mendapatkan nama field
        message = error.get("msg")    # Mendapatkan pesan kesalahan
        errors.append(f"Field '{field}': {message}")

    error_message = "\n".join(errors)

    return JSONResponse(
        status_code=422,
        content={
            "status": False,
            "status_code": "422 Unprocessable Entity",
            "message": error_message
        },
    )

app.include_router(api_router, prefix=settings.API_V1_STR)