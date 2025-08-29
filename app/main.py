from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
import time
import traceback
import logging
from app.api.routes import router
from app.core.exceptions import (
    MarksheetExtractionException,
    marksheet_exception_handler,
    validation_exception_handler
)
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Marksheet Extractor API",
    description="AI-based API for extracting structured data from marksheets",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Add exception handlers
app.add_exception_handler(MarksheetExtractionException, marksheet_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(f"Full traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}", "traceback": traceback.format_exc()}
    )

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Request: {request.url} completed in {process_time:.4f}s")
    return response

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Root endpoint that shows a test page
    """
    try:
        with open("templates/welcome.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Marksheet Extractor API</h1><p>Test page not found. Please create templates/test.html</p>")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Test endpoint to check if Gemini API key is set
@app.get("/test-gemini")
async def test_gemini():
    try:
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            return {"status": "error", "message": "Gemini API key is not set properly"}
        return {"status": "success", "message": "Gemini API key is set"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Test endpoint to list available models
@app.get("/test-models")
async def test_models():
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        models = [m.name for m in genai.list_models()]
        return {"status": "success", "models": models}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)