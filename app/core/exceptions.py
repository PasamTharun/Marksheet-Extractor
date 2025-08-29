from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Union, Dict, Any

class MarksheetExtractionException(HTTPException):
    """
    Custom exception for marksheet extraction errors
    """
    def __init__(self, status_code: int, detail: Any = None, headers: Dict[str, str] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

async def marksheet_exception_handler(request: Request, exc: MarksheetExtractionException):
    """
    Handler for MarksheetExtractionException
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for RequestValidationError
    """
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "status_code": 422}
    )