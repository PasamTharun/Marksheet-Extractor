from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from typing import List, Optional
import os
import uuid
import shutil
import time
from app.api.schemas import (
    ExtractionResponse, 
    BatchExtractionResponse,
    HealthResponse
)
from app.services.extractor import MarksheetExtractor
from app.core.config import settings
from app.core.exceptions import MarksheetExtractionException
from app.utils.file_utils import validate_file, get_temp_file_path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/extract", response_model=ExtractionResponse)
async def extract_marksheet(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Extract structured data from a single marksheet (JPG/PNG/PDF)
    """
    try:
        # Validate file
        validate_file(file)
        
        # Create temporary file
        temp_file_path = get_temp_file_path(file.filename)
        
        # Save uploaded file to temp location
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract data
        extractor = MarksheetExtractor()
        start_time = time.time()
        result_dict = await extractor.extract(temp_file_path)
        processing_time = time.time() - start_time
        
        # Schedule cleanup
        background_tasks.add_task(os.remove, temp_file_path)
        
        # Create response with additional metadata
        result = ExtractionResponse(
            candidate_details=result_dict["candidate_details"],
            subjects=result_dict["subjects"],
            overall_result=result_dict["overall_result"],
            issue_details=result_dict["issue_details"],
            processing_time=processing_time,
            file_type=file.content_type,
            file_size=file.size
        )
        
        return result
        
    except MarksheetExtractionException as e:
        logger.error(f"Marksheet extraction error: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error during extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/batch-extract", response_model=BatchExtractionResponse)
async def batch_extract_marksheets(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """
    Extract structured data from multiple marksheets in batch
    """
    try:
        if len(files) > settings.MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"Batch size exceeds maximum limit of {settings.MAX_BATCH_SIZE}"
            )
        
        results = []
        temp_file_paths = []
        
        # Process each file
        for file in files:
            try:
                # Validate file
                validate_file(file)
                
                # Create temporary file
                temp_file_path = get_temp_file_path(file.filename)
                temp_file_paths.append(temp_file_path)
                
                # Save uploaded file to temp location
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Extract data
                extractor = MarksheetExtractor()
                start_time = time.time()
                result_dict = await extractor.extract(temp_file_path)
                processing_time = time.time() - start_time
                
                # Create response with additional metadata
                result = ExtractionResponse(
                    candidate_details=result_dict["candidate_details"],
                    subjects=result_dict["subjects"],
                    overall_result=result_dict["overall_result"],
                    issue_details=result_dict["issue_details"],
                    processing_time=processing_time,
                    file_type=file.content_type,
                    file_size=file.size
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing {file.filename}: {str(e)}")
                results.append({
                    "error": f"Error processing {file.filename}: {str(e)}",
                    "filename": file.filename
                })
        
        # Schedule cleanup
        for temp_file_path in temp_file_paths:
            background_tasks.add_task(os.remove, temp_file_path)
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Error during batch extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "version": "1.0.0"}