import pytest
import os
import json
from fastapi.testclient import TestClient
from fastapi import status
from app.main import app

client = TestClient(app)

@pytest.fixture
def sample_image_path():
    return os.path.join("samples", "sample1.jpg")

@pytest.fixture
def sample_pdf_path():
    return os.path.join("samples", "sample3.pdf")

def test_health_check():
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"

def test_extract_valid_image(sample_image_path):
    with open(sample_image_path, "rb") as f:
        response = client.post("/api/v1/extract", files={"file": ("sample.jpg", f, "image/jpeg")})
    
    assert response.status_code == status.HTTP_200_OK
    
    # Validate response structure
    data = response.json()
    assert "candidate_details" in data
    assert "subjects" in data
    assert "overall_result" in data
    assert "issue_details" in data
    assert "processing_time" in data
    assert "file_type" in data
    assert "file_size" in data
    
    # Validate candidate details
    candidate_details = data["candidate_details"]
    assert "name" in candidate_details
    assert "father_name" in candidate_details
    assert "dob" in candidate_details
    assert "roll_no" in candidate_details
    assert "registration_no" in candidate_details
    assert "exam_year" in candidate_details
    assert "board" in candidate_details
    assert "institution" in candidate_details
    
    # Validate subjects
    subjects = data["subjects"]
    assert isinstance(subjects, list)
    for subject in subjects:
        assert "subject" in subject
        assert "confidence" in subject
        assert 0 <= subject["confidence"] <= 1
    
    # Validate overall result
    overall_result = data["overall_result"]
    assert "division" in overall_result
    
    # Validate issue details
    issue_details = data["issue_details"]
    assert "date" in issue_details or "place" in issue_details

def test_extract_valid_pdf(sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        response = client.post("/api/v1/extract", files={"file": ("sample.pdf", f, "application/pdf")})
    
    assert response.status_code == status.HTTP_200_OK
    
    # Validate response structure
    data = response.json()
    assert "candidate_details" in data
    assert "subjects" in data
    assert "overall_result" in data
    assert "issue_details" in data

def test_extract_invalid_file_type():
    # Create a text file
    content = b"This is a text file, not an image or PDF"
    response = client.post(
        "/api/v1/extract", 
        files={"file": ("sample.txt", content, "text/plain")}
    )
    
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE

def test_extract_large_file():
    # Create a large file (11 MB)
    content = b"x" * (11 * 1024 * 1024)
    response = client.post(
        "/api/v1/extract", 
        files={"file": ("large.jpg", content, "image/jpeg")}
    )
    
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

def test_batch_extract(sample_image_path, sample_pdf_path):
    files = [
        ("files", ("sample.jpg", open(sample_image_path, "rb"), "image/jpeg")),
        ("files", ("sample.pdf", open(sample_pdf_path, "rb"), "application/pdf"))
    ]
    
    response = client.post("/api/v1/batch-extract", files=files)
    
    assert response.status_code == status.HTTP_200_OK
    
    # Validate response structure
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    
    # Validate each result
    for result in data["results"]:
        assert "candidate_details" in result
        assert "subjects" in result
        assert "overall_result" in result
        assert "issue_details" in result

def test_batch_extract_too_many_files(sample_image_path):
    # Create 11 files (exceeds MAX_BATCH_SIZE of 10)
    files = [("files", (f"sample{i}.jpg", open(sample_image_path, "rb"), "image/jpeg")) for i in range(11)]
    
    response = client.post("/api/v1/batch-extract", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST