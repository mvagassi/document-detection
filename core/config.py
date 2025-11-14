from pydantic_settings import BaseSettings
from typing import ClassVar

class Settings(BaseSettings):
    API_V1_STR: str = "/api/api_v1"
    env: ClassVar[str] = 'dev'  # Ditandai sebagai ClassVar
    environment_route: ClassVar[str] = 'dev'
    
    class Config:  # Harus diawali huruf besar
        case_sensitive = True

settings = Settings()
