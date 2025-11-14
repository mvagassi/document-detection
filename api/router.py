from fastapi import APIRouter
from core.config import settings
from .api_v1.endpoints.document import document_checker

api_router = APIRouter()
ENV_ROUTE = settings.environment_route in ["dev", "local"]
api_router.include_router(document_checker.router, tags=["Document Checker"])