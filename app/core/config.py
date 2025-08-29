import os
import json
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    ALLOWED_ORIGINS: List[str] = json.loads(os.getenv("ALLOWED_ORIGINS", '["*"]'))
    
    # File Upload Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_FILE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
    MAX_BATCH_SIZE: int = 10
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-pro"
    
    # OCR Settings
    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "")
    
    # Temp Directory
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp")
    
    class Config:
        env_file = ".env"

settings = Settings()