import os
import uuid
from typing import List
from fastapi import UploadFile, HTTPException
from app.core.config import settings
from app.core.exceptions import MarksheetExtractionException

def validate_file(file: UploadFile) -> None:
    """
    Validate uploaded file
    
    Args:
        file: Uploaded file
        
    Raises:
        MarksheetExtractionException: If file is invalid
    """
    # Check file size
    if file.size > settings.MAX_FILE_SIZE:
        raise MarksheetExtractionException(
            status_code=413,
            detail=f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE / (1024 * 1024)} MB"
        )
    
    # Check file type
    if file.content_type not in settings.ALLOWED_FILE_TYPES:
        raise MarksheetExtractionException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}"
        )

def get_temp_file_path(filename: str) -> str:
    """
    Generate a temporary file path
    
    Args:
        filename: Original filename
        
    Returns:
        str: Temporary file path
    """
    # Create temp directory if it doesn't exist
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    # Return full path
    return os.path.join(settings.TEMP_DIR, unique_filename)