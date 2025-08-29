from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class SubjectMarks(BaseModel):
    subject: Optional[str] = Field(None, description="Name of the subject")
    max_marks: Optional[float] = Field(None, description="Maximum marks or credits for the subject")
    obtained_marks: Optional[float] = Field(None, description="Marks or credits obtained by the candidate")
    grade: Optional[str] = Field(None, description="Grade if available")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")

class CandidateDetails(BaseModel):
    name: Dict[str, Any] = Field(..., example={"value": "John Doe", "confidence": 0.98})
    father_name: Dict[str, Any] = Field(..., example={"value": "Richard Roe", "confidence": 0.95})
    dob: Dict[str, Any] = Field(..., example={"value": "01-01-2000", "confidence": 0.97})
    roll_no: Dict[str, Any] = Field(..., example={"value": "12345", "confidence": 0.99})
    registration_no: Dict[str, Any] = Field(..., example={"value": "REG123", "confidence": 0.96})
    exam_year: Dict[str, Any] = Field(..., example={"value": "2023", "confidence": 0.94})
    board: Dict[str, Any] = Field(..., example={"value": "CBSE", "confidence": 0.95})
    institution: Dict[str, Any] = Field(..., example={"value": "ABC School", "confidence": 0.93})

class OverallResult(BaseModel):
    division: Dict[str, Any] = Field(..., example={"value": "First", "confidence": 0.96})
    percentage: Optional[Dict[str, Any]] = Field(None, example={"value": "85.5", "confidence": 0.95})
    grade: Optional[Dict[str, Any]] = Field(None, example={"value": "A", "confidence": 0.94})

class IssueDetails(BaseModel):
    date: Optional[Dict[str, Any]] = Field(None, example={"value": "01-06-2023", "confidence": 0.92})
    place: Optional[Dict[str, Any]] = Field(None, example={"value": "Delhi", "confidence": 0.92})

class ExtractionResponse(BaseModel):
    candidate_details: CandidateDetails
    subjects: List[SubjectMarks]
    overall_result: OverallResult
    issue_details: IssueDetails
    processing_time: float = Field(..., description="Processing time in seconds")
    file_type: str = Field(..., description="Type of input file")
    file_size: int = Field(..., description="Size of input file in bytes")

class BatchExtractionResponse(BaseModel):
    results: List[ExtractionResponse]

class HealthResponse(BaseModel):
    status: str
    version: str

# Request models (not used in current implementation but kept for completeness)
class ExtractionRequest(BaseModel):
    """Request model for single marksheet extraction"""
    pass  # We're using UploadFile directly, so this isn't needed

class BatchExtractionRequest(BaseModel):
    """Request model for batch marksheet extraction"""
    pass  # We're using List[UploadFile] directly, so this isn't needed