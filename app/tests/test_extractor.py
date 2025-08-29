import pytest
import os
import json
from unittest.mock import AsyncMock, patch
from app.services.extractor import MarksheetExtractor
from app.services.ocr import OCRService
from app.services.llm import LLMService

@pytest.fixture
def mock_ocr_result():
    return {
        "text": """
        CENTRAL BOARD OF SECONDARY EDUCATION
        CERTIFICATE
        This is to certify that
        
        JOHN DOE
        S/O RICHARD ROE
        
        has completed the course of study prescribed for the
        Secondary School Examination held in March 2023
        
        Date of Birth: 01-01-2005
        Roll Number: 1234567
        Registration Number: REG123456
        
        School: ABC SCHOOL, DELHI
        
        SUBJECTS        MAX MARKS   OBTAINED MARKS   GRADE
        Mathematics      100         95               A1
        Science          100         90               A2
        English          100         85               B1
        Social Science   100         80               B1
        
        RESULT: PASS
        DIVISION: FIRST
        
        Date of Issue: 01-06-2023
        Place: DELHI
        """,
        "metadata": {
            "type": "image",
            "format": "JPEG",
            "size": (800, 600),
            "mode": "RGB"
        }
    }

@pytest.fixture
def mock_llm_result():
    return {
        "candidate_details": {
            "name": "JOHN DOE",
            "father_name": "RICHARD ROE",
            "dob": "01-01-2005",
            "roll_no": "1234567",
            "registration_no": "REG123456",
            "exam_year": "2023",
            "board": "CENTRAL BOARD OF SECONDARY EDUCATION",
            "institution": "ABC SCHOOL, DELHI"
        },
        "subjects": [
            {
                "subject": "Mathematics",
                "max_marks": 100,
                "obtained_marks": 95,
                "grade": "A1"
            },
            {
                "subject": "Science",
                "max_marks": 100,
                "obtained_marks": 90,
                "grade": "A2"
            },
            {
                "subject": "English",
                "max_marks": 100,
                "obtained_marks": 85,
                "grade": "B1"
            },
            {
                "subject": "Social Science",
                "max_marks": 100,
                "obtained_marks": 80,
                "grade": "B1"
            }
        ],
        "overall_result": {
            "division": "FIRST",
            "percentage": None,
            "grade": None
        },
        "issue_details": {
            "date": "01-06-2023",
            "place": "DELHI"
        }
    }

@pytest.mark.asyncio
async def test_extract_success(mock_ocr_result, mock_llm_result):
    extractor = MarksheetExtractor()
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    extractor.llm_service.extract_structured_data = AsyncMock(return_value=mock_llm_result)
    
    result = await extractor.extract("dummy_path.jpg")
    
    assert "candidate_details" in result
    assert "subjects" in result
    assert "overall_result" in result
    assert "issue_details" in result
    
    candidate_details = result["candidate_details"]
    assert "name" in candidate_details
    assert "father_name" in candidate_details
    assert "dob" in candidate_details
    assert "roll_no" in candidate_details
    assert "registration_no" in candidate_details
    assert "exam_year" in candidate_details
    assert "board" in candidate_details
    assert "institution" in candidate_details
    
    for field in candidate_details.values():
        assert "value" in field
        assert "confidence" in field
        assert 0 <= field["confidence"] <= 1
    
    subjects = result["subjects"]
    assert len(subjects) == 4
    
    for subject in subjects:
        assert "subject" in subject
        assert "max_marks" in subject
        assert "obtained_marks" in subject
        assert "grade" in subject
        assert "confidence" in subject
        assert 0 <= subject["confidence"] <= 1
    
    overall_result = result["overall_result"]
    assert "division" in overall_result
    assert 0 <= overall_result["division"]["confidence"] <= 1
    
    issue_details = result["issue_details"]
    assert "date" in issue_details
    assert "place" in issue_details
    assert 0 <= issue_details["date"]["confidence"] <= 1
    assert 0 <= issue_details["place"]["confidence"] <= 1

@pytest.mark.asyncio
async def test_extract_ocr_failure():
    extractor = MarksheetExtractor()
    
    extractor.ocr_service.extract_text = AsyncMock(side_effect=Exception("OCR failed"))
    
    with pytest.raises(Exception) as excinfo:
        await extractor.extract("dummy_path.jpg")
    
    assert "OCR failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_extract_llm_failure(mock_ocr_result):
    extractor = MarksheetExtractor()
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    extractor.llm_service.extract_structured_data = AsyncMock(side_effect=Exception("LLM failed"))
    
    with pytest.raises(Exception) as excinfo:
        await extractor.extract("dummy_path.jpg")
    
    assert "LLM failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_extract_wb_madhyamik_marksheet():
    extractor = MarksheetExtractor()
    
    mock_ocr_result = {
        "text": """
        WEST BENGAL BOARD OF SECONDARY EDUCATION
        MADHYAMIK PARIKSHA (SECONDAKY EXAMINATION) 2007
        
        CANDIDATE'S COPY
        
        Roll No: F06931
        Name of Candidate: NARAYAN DEBNATH
        Father's Name: GOPINATH DEBNATH
        
        School: SIBPUR DINABANDHU INSTITUTION (BRANCH)
        
        SUBJECTS
        Language: 156
        Science: 214
        India & People: 112
        Additional: 33
        
        Total: 515
        
        Result: FIRST Division
        
        Date: 31-05-2007
        Place: Kolkata
        """,
        "metadata": {
            "type": "image",
            "format": "JPEG",
            "size": (800, 600),
            "mode": "RGB"
        }
    }
    
    extractor.llm_service.extract_structured_data = AsyncMock(return_value={
        "candidate_details": {
            "name": "NARAYAN DEBNATH",
            "father_name": "GOPINATH DEBNATH",
            "dob": None,
            "roll_no": "F06931",
            "registration_no": None,
            "exam_year": "2007",
            "board": "WEST BENGAL BOARD OF SECONDARY EDUCATION",
            "institution": "SIBPUR DINABANDHU INSTITUTION (BRANCH)"
        },
        "subjects": [],
        "overall_result": {
            "division": "FIRST",
            "percentage": None,
            "grade": None
        },
        "issue_details": {
            "date": None,
            "place": None
        }
    })
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    
    result = await extractor.extract("dummy_path.jpg")
    
    assert len(result["subjects"]) == 4
    
    subject_names = [s["subject"]["value"] for s in result["subjects"]]
    assert "Language" in subject_names
    assert "Science" in subject_names
    assert "India & People" in subject_names
    assert "Additional" in subject_names
    
    for subject in result["subjects"]:
        assert subject["obtained_marks"]["value"] is not None
        assert subject["obtained_marks"]["value"] > 0
    
    assert result["candidate_details"]["name"]["value"] == "NARAYAN DEBNATH"
    assert result["candidate_details"]["roll_no"]["value"] == "F06931"
    assert result["overall_result"]["division"]["value"] == "FIRST"
    assert result["issue_details"]["date"]["value"] == "31-05-2007"
    assert result["issue_details"]["place"]["value"] == "Kolkata"

@pytest.mark.asyncio
async def test_extract_cbse_format():
    extractor = MarksheetExtractor()
    
    mock_ocr_result = {
        "text": """
        CENTRAL BOARD OF SECONDARY EDUCATION
        SECONDARY SCHOOL EXAMINATION 2023
        
        CANDIDATE INFORMATION
        Name: RAMESH KUMAR
        Father's Name: SURESH KUMAR
        Date of Birth: 15-07-2008
        Roll Number: 1234567
        Registration Number: CBSE202312345
        
        SCHOOL DETAILS
        School Name: DELHI PUBLIC SCHOOL
        Board: CBSE
        
        SUBJECT WISE PERFORMANCE
        Subject | Maximum Marks | Marks Obtained | Grade
        Mathematics | 100 | 95 | A1
        Science | 100 | 92 | A1
        English | 100 | 88 | A2
        Social Science | 100 | 85 | B1
        Hindi | 100 | 90 | A2
        
        RESULT
        Division: First Division
        Percentage: 90.0%
        
        CERTIFICATE DETAILS
        Date of Issue: 20-05-2023
        Place: New Delhi
        """,
        "metadata": {"type": "image", "format": "JPEG"}
    }
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    extractor.llm_service.extract_structured_data = AsyncMock(return_value={
        "candidate_details": {
            "name": "RAMESH KUMAR",
            "father_name": "SURESH KUMAR",
            "dob": "15-07-2008",
            "roll_no": "1234567",
            "registration_no": "CBSE202312345",
            "exam_year": "2023",
            "board": "CBSE",
            "institution": "DELHI PUBLIC SCHOOL"
        },
        "subjects": [],
        "overall_result": {
            "division": "First Division",
            "percentage": None,
            "grade": None
        },
        "issue_details": {
            "date": None,
            "place": None
        }
    })
    
    result = await extractor.extract("dummy_path.jpg")
    
    assert result["candidate_details"]["name"]["value"] == "RAMESH KUMAR"
    assert len(result["subjects"]) == 5
    assert result["overall_result"]["division"]["value"] == "First Division"
    assert result["overall_result"]["percentage"]["value"] == 90.0
    assert result["issue_details"]["date"]["value"] == "20-05-2023"
    assert result["issue_details"]["place"]["value"] == "New Delhi"

@pytest.mark.asyncio
async def test_extract_icse_format():
    extractor = MarksheetExtractor()
    
    mock_ocr_result = {
        "text": """
        COUNCIL FOR THE INDIAN SCHOOL CERTIFICATE EXAMINATIONS
        ICSE YEAR 2023 EXAMINATION
        
        Candidate Details
        Name: PRIYA SHARMA
        Father's Name: RAJESH SHARMA
        DOB: 22-11-2007
        UID: 2023ICSE12345
        
        School: ST. XAVIER'S SCHOOL
        Board: CISCE
        
        Subject Performance
        English - 90
        Mathematics - 85
        Physics - 88
        Chemistry - 92
        Biology - 87
        History - 82
        Geography - 85
        
        Result
        Grade: Distinction
        Percentage: 87.0%
        
        Issued on: 15-06-2023
        At: Mumbai
        """,
        "metadata": {"type": "image", "format": "JPEG"}
    }
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    extractor.llm_service.extract_structured_data = AsyncMock(return_value={
        "candidate_details": {
            "name": "PRIYA SHARMA",
            "father_name": "RAJESH SHARMA",
            "dob": "22-11-2007",
            "roll_no": None,
            "registration_no": "2023ICSE12345",
            "exam_year": "2023",
            "board": "CISCE",
            "institution": "ST. XAVIER'S SCHOOL"
        },
        "subjects": [],
        "overall_result": {
            "division": None,
            "percentage": None,
            "grade": "Distinction"
        },
        "issue_details": {
            "date": None,
            "place": None
        }
    })
    
    result = await extractor.extract("dummy_path.jpg")
    
    assert result["candidate_details"]["name"]["value"] == "PRIYA SHARMA"
    assert len(result["subjects"]) == 7
    assert result["overall_result"]["grade"]["value"] == "Distinction"
    assert result["overall_result"]["percentage"]["value"] == 87.0
    assert result["issue_details"]["date"]["value"] == "15-06-2023"
    assert result["issue_details"]["place"]["value"] == "Mumbai"

@pytest.mark.asyncio
async def test_extract_state_board_format():
    extractor = MarksheetExtractor()
    
    mock_ocr_result = {
        "text": """
        MAHARASHTRA STATE BOARD OF SECONDARY EDUCATION
        SSC EXAMINATION MARCH 2023
        
        STUDENT INFORMATION
        Name: AJAY PATIL
        Mother's Name: SUNITA PATIL
        Birth Date: 05-09-2008
        Seat No: M2023123456
        
        College: NEW ENGLISH SCHOOL
        Division: Pune
        
        SUBJECT MARKS
        Marathi: 85
        Hindi: 78
        English: 82
        Mathematics: 90
        Science: 88
        Social Science: 84
        
        RESULT
        Class: First Class
        Total Marks: 507/600
        
        Date: 10-06-2023
        Place: Pune
        """,
        "metadata": {"type": "image", "format": "JPEG"}
    }
    
    extractor.ocr_service.extract_text = AsyncMock(return_value=mock_ocr_result)
    extractor.llm_service.extract_structured_data = AsyncMock(return_value={
        "candidate_details": {
            "name": "AJAY PATIL",
            "father_name": None,
            "dob": "05-09-2008",
            "roll_no": "M2023123456",
            "registration_no": None,
            "exam_year": "2023",
            "board": "MAHARASHTRA STATE BOARD",
            "institution": "NEW ENGLISH SCHOOL"
        },
        "subjects": [],
        "overall_result": {
            "division": "First Class",
            "percentage": None,
            "grade": None
        },
        "issue_details": {
            "date": None,
            "place": None
        }
    })
    
    result = await extractor.extract("dummy_path.jpg")
    
    assert result["candidate_details"]["name"]["value"] == "AJAY PATIL"
    assert len(result["subjects"]) == 6
    assert result["overall_result"]["division"]["value"] == "First Class"
    assert result["issue_details"]["date"]["value"] == "10-06-2023"
    assert result["issue_details"]["place"]["value"] == "Pune"