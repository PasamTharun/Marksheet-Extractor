import os
import json
import re
import traceback
from typing import Dict, Any, List, Optional
import asyncio
from app.services.ocr import OCRService
from app.services.llm import LLMService
from app.utils.confidence import calculate_confidence
from app.api.schemas import (
    ExtractionResponse, 
    CandidateDetails, 
    SubjectMarks, 
    OverallResult, 
    IssueDetails
)
from app.core.exceptions import MarksheetExtractionException
import logging

logger = logging.getLogger(__name__)

class MarksheetExtractor:
    """
    Main class for extracting structured data from marksheets
    """
    def __init__(self):
        self.ocr_service = OCRService()
        self.llm_service = LLMService()
    
    async def extract(self, file_path: str) -> Dict[str, Any]:
        """
        Extract structured data from a marksheet file
        
        Args:
            file_path: Path to the marksheet file (JPG/PNG/PDF)
            
        Returns:
            Dict: Structured data extracted from the marksheet
        """
        try:
            logger.info(f"Starting extraction for file: {file_path}")
            logger.info(f"File exists: {os.path.exists(file_path)}")
            logger.info(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'N/A'} bytes")
            
            # Extract text using OCR
            logger.info("Starting OCR extraction")
            ocr_result = await self.ocr_service.extract_text(file_path)
            logger.info(f"OCR extraction completed. Text length: {len(ocr_result.get('text', ''))}")
            
            # DEBUG: Save OCR result to logs
            logger.info(f"Full OCR text: {ocr_result.get('text', '')}")
            
            # Extract structured data using LLM
            logger.info("Starting LLM extraction")
            structured_data = await self.llm_service.extract_structured_data(
                ocr_result["text"], 
                ocr_result.get("metadata", {})
            )
            logger.info(f"LLM extraction completed. Data keys: {list(structured_data.keys())}")
            logger.debug(f"LLM structured data: {json.dumps(structured_data, indent=2)}")
            
            # Fallback for subjects if LLM didn't extract any
            if not structured_data.get("subjects"):
                logger.warning("LLM didn't extract subjects, using fallback method")
                structured_data["subjects"] = self._extract_subjects_fallback(ocr_result["text"])
                logger.info(f"Fallback extracted {len(structured_data['subjects'])} subjects")
            
            # Post-process to extract missing fields
            logger.info("Starting post-processing for missing fields")
            structured_data = self._post_process_missing_fields(structured_data, ocr_result["text"])
            logger.info("Post-processing completed")
            
            # Calculate confidence scores
            logger.info("Starting confidence calculation")
            result_with_confidence = await self._add_confidence_scores(
                structured_data, 
                ocr_result
            )
            logger.info("Confidence calculation completed")
            
            # Validate and clean data
            logger.info("Starting data validation")
            validated_data = self._validate_and_clean_data(result_with_confidence)
            logger.info("Data validation completed")
            
            logger.info("Extraction completed successfully")
            return validated_data
            
        except MarksheetExtractionException as e:
            logger.error(f"Marksheet extraction error: {str(e)}")
            logger.error(f"Error details: {traceback.format_exc()}")
            raise MarksheetExtractionException(
                status_code=500, 
                detail=f"Error during extraction: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during extraction: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise MarksheetExtractionException(
                status_code=500, 
                detail=f"Error during extraction: {str(e)}"
            )
    
    def _extract_subjects_fallback(self, ocr_text: str) -> List[Dict[str, Any]]:
        logger.info("Using fallback subject extraction")
        logger.info(f"OCR text for fallback: {ocr_text}")
        subjects = []
        
        # First, look for the specific expected subjects
        expected_patterns = [
            (r'FIRST LANGUAGE\s*[:\-]?\s*(\d+)', "FIRST LANGUAGE"),
            (r'SECOND LANGUAGE\s*[:\-]?\s*(\d+)', "SECOND LANGUAGE"),
            (r'MATHS\s*[:\-]?\s*(\d+)', "MATHS"),
            (r'SCIENCE\s*[:\-]?\s*(\d+)', "SCIENCE"),
            (r'HISTORY\s*\(WRITTEN\)\s*[:\-]?\s*(\d+)', "HISTORY (WRITTEN)"),
            (r'HISTORY\s*\(ORAL\)\s*[:\-]?\s*(\d+)', "HISTORY (ORAL)"),
            (r'GEOGRAPHY\s*\(WRITTEN\)\s*[:\-]?\s*(\d+)', "GEOGRAPHY (WRITTEN)"),
            (r'GEOGRAPHY\s*\(ORAL\)\s*[:\-]?\s*(\d+)', "GEOGRAPHY (ORAL)"),
        ]
        
        for pattern, subject_name in expected_patterns:
            matches = re.findall(pattern, ocr_text, re.IGNORECASE)
            logger.debug(f"Pattern '{pattern}' found {len(matches)} matches for subject '{subject_name}'")
            for match in matches:
                if match.isdigit():
                    subjects.append({
                        "subject": subject_name,
                        "max_marks": None,
                        "obtained_marks": int(match),
                        "grade": None
                    })
        
        # If we found the expected subjects, return them
        if len(subjects) >= 3:
            logger.info(f"Found {len(subjects)} expected subjects, returning them")
            return subjects
        
        # Otherwise, fall back to generic patterns
        logger.info("Not enough expected subjects found, using generic patterns")
        table_patterns = [
            r'([A-Za-z\s&]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([A-Za-z0-9+-]*)',
            r'([A-Za-z\s&]+)\s+(\d+)\s+(\d+)\s+([A-Za-z0-9+-]*)',
            r'([A-Za-z\s&]+):\s*(\d+)\s*/\s*(\d+)',
            r'([A-Za-z\s&]+)\s*-\s*(\d+)',
            r'([A-Za-z\s&]+)\s+(\d+)',  # Simple pattern: SubjectName Marks
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, ocr_text, re.IGNORECASE)
            logger.debug(f"Generic pattern '{pattern}' found {len(matches)} matches")
            if matches:
                for match in matches:
                    if len(match) == 4:
                        subject_name = match[0].strip()
                        max_marks = match[1].strip()
                        obtained_marks = match[2].strip()
                        grade = match[3].strip() if match[3] else None
                        
                        if self._is_valid_subject(subject_name):
                            subjects.append({
                                "subject": subject_name,
                                "max_marks": int(max_marks) if max_marks.isdigit() else None,
                                "obtained_marks": int(obtained_marks) if obtained_marks.isdigit() else None,
                                "grade": grade
                            })
                    
                    elif len(match) == 3:
                        subject_name = match[0].strip()
                        obtained_marks = match[1].strip()
                        max_marks = match[2].strip()
                        
                        if self._is_valid_subject(subject_name):
                            subjects.append({
                                "subject": subject_name,
                                "max_marks": int(max_marks) if max_marks.isdigit() else None,
                                "obtained_marks": int(obtained_marks) if obtained_marks.isdigit() else None,
                                "grade": None
                            })
                    
                    elif len(match) == 2:
                        subject_name = match[0].strip()
                        marks = match[1].strip()
                        
                        if self._is_valid_subject(subject_name):
                            subjects.append({
                                "subject": subject_name,
                                "max_marks": None,
                                "obtained_marks": int(marks) if marks.isdigit() else None,
                                "grade": None
                            })
        
        # Line-by-line parsing for any subject pattern
        lines = ocr_text.split('\n')
        for line in lines:
            # Try different subject patterns
            subject_patterns = [
                r'([A-Za-z\s&]+)\s*[:\-]?\s*(\d+)',  # Subject: Marks
                r'([A-Za-z\s&]+)\s+(\d+)',  # Subject Marks
                r'([A-Za-z\s&]+)\s*(\d+)\s*/\s*(\d+)',  # Subject: Marks/Max
            ]
            
            for pattern in subject_patterns:
                match = re.search(pattern, line)
                if match:
                    subject_name = match.group(1).strip()
                    
                    if len(match.groups()) == 2:  # Simple pattern
                        marks = match.group(2).strip()
                        if self._is_valid_subject(subject_name):
                            subjects.append({
                                "subject": subject_name,
                                "max_marks": None,
                                "obtained_marks": int(marks) if marks.isdigit() else None,
                                "grade": None
                            })
                    
                    elif len(match.groups()) == 3:  # Subject: Marks/Max
                        obtained_marks = match.group(2).strip()
                        max_marks = match.group(3).strip()
                        if self._is_valid_subject(subject_name):
                            subjects.append({
                                "subject": subject_name,
                                "max_marks": int(max_marks) if max_marks.isdigit() else None,
                                "obtained_marks": int(obtained_marks) if obtained_marks.isdigit() else None,
                                "grade": None
                            })
        
        logger.info(f"Generic extraction found {len(subjects)} subjects: {[s['subject'] for s in subjects]}")
        return subjects
    
    def _is_valid_subject(self, subject_name: str) -> bool:
        exclude_terms = [
            'total', 'grand total', 'result', 'division', 'percentage',
            'grade', 'marks', 'obtained', 'maximum', 'subject', 'name',
            'roll', 'registration', 'board', 'school', 'college', 'first', 'second'
        ]
        
        subject_lower = subject_name.lower()
        
        if any(term in subject_lower for term in exclude_terms):
            return False
        
        if len(subject_name) < 3 or not subject_name[0].isalpha():
            return False
        
        letter_ratio = sum(c.isalpha() for c in subject_name) / len(subject_name)
        return letter_ratio > 0.5
    
    def _post_process_missing_fields(self, data: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
        logger.info("Post-processing missing fields")
        logger.info(f"OCR text for post-processing: {ocr_text}")
        
        # Extract name if missing
        if not data["candidate_details"]["name"]:
            name_patterns = [
                r'Name[:\s]+([A-Za-z\s]+)',
                r'Candidate[:\s]+([A-Za-z\s]+)',
                r'Student[:\s]+([A-Za-z\s]+)',
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["name"] = match.group(1).strip()
                    logger.info(f"Found name: {match.group(1)}")
                    break
        
        # Extract father_name if missing
        if not data["candidate_details"]["father_name"]:
            father_patterns = [
                r'Father\'s Name[:\s]+([A-Za-z\s]+)',
                r'Father[:\s]+([A-Za-z\s]+)',
                r'S/O[:\s]+([A-Za-z\s]+)',
            ]
            
            for pattern in father_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["father_name"] = match.group(1).strip()
                    logger.info(f"Found father name: {match.group(1)}")
                    break
        
        # Extract DOB if missing
        if not data["candidate_details"]["dob"]:
            dob_patterns = [
                r'Date of Birth[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'DOB[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'Birth[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'Born[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*(?i:DOB|Birth|Born)',
            ]
            
            for pattern in dob_patterns:
                match = re.search(pattern, ocr_text)
                if match:
                    dob = match.group(1)
                    dob = re.sub(r'[/]', '-', dob)
                    data["candidate_details"]["dob"] = dob
                    logger.info(f"Found DOB: {dob}")
                    break
        
        # Extract roll_no if missing
        if not data["candidate_details"]["roll_no"]:
            roll_patterns = [
                r'Roll No[:\s]+([A-Za-z0-9\-\/]+)',
                r'Roll Number[:\s]+([A-Za-z0-9\-\/]+)',
                r'Roll[:\s]+([A-Za-z0-9\-\/]+)',
            ]
            
            for pattern in roll_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["roll_no"] = match.group(1).strip()
                    logger.info(f"Found roll number: {match.group(1)}")
                    break
        
        # Extract registration_no if missing
        if not data["candidate_details"]["registration_no"]:
            reg_patterns = [
                r'Registration No[:\s]+([A-Za-z0-9\-\/]+)',
                r'Reg\. No[:\s]+([A-Za-z0-9\-\/]+)',
                r'Reg[:\s]+([A-Za-z0-9\-\/]+)',
                r'Registration[:\s]+([A-Za-z0-9\-\/]+)',
            ]
            
            for pattern in reg_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["registration_no"] = match.group(1).strip()
                    logger.info(f"Found registration number: {match.group(1)}")
                    break
        
        # Extract exam_year if missing
        if not data["candidate_details"]["exam_year"]:
            year_patterns = [
                r'Year[:\s]+(19|20\d{2})',
                r'Exam Year[:\s]+(19|20\d{2})',
                r'Examination Year[:\s]+(19|20\d{2})',
                r'(19|20\d{2})\s*(?i:Year|Exam)',
            ]
            
            for pattern in year_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["exam_year"] = match.group(1)
                    logger.info(f"Found exam year: {match.group(1)}")
                    break
        
        # Extract board if missing
        if not data["candidate_details"]["board"]:
            board_patterns = [
                r'Board[:\s]+([A-Za-z\s&\-]+)',
                r'University[:\s]+([A-Za-z\s&\-]+)',
                r'Council[:\s]+([A-Za-z\s&\-]+)',
            ]
            
            for pattern in board_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["board"] = match.group(1).strip()
                    logger.info(f"Found board: {match.group(1)}")
                    break
        
        # Extract institution if missing
        if not data["candidate_details"]["institution"]:
            institution_patterns = [
                r'School[:\s]+([A-Za-z\s&\-\.]+)',
                r'College[:\s]+([A-Za-z\s&\-\.]+)',
                r'Institution[:\s]+([A-Za-z\s&\-\.]+)',
            ]
            
            for pattern in institution_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["candidate_details"]["institution"] = match.group(1).strip()
                    logger.info(f"Found institution: {match.group(1)}")
                    break
        
        # Extract division if missing
        if not data["overall_result"]["division"]:
            division_patterns = [
                r'Division[:\s]+(First|Second|Third|Distinction)',
                r'Class[:\s]+(First|Second|Third|Distinction)',
                r'Result[:\s]+(First|Second|Third|Distinction)',
            ]
            
            for pattern in division_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["overall_result"]["division"] = match.group(1)
                    logger.info(f"Found division: {match.group(1)}")
                    break
        
        # Extract percentage if missing
        if not data["overall_result"]["percentage"]:
            percentage_patterns = [
                r'Percentage[:\s]+(\d+(?:\.\d+)?)%',
                r'(\d+(?:\.\d+)?)%\s*(?i:Percentage|Percent)',
                r'Overall[:\s]+(\d+(?:\.\d+)?)%',
            ]
            
            for pattern in percentage_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["overall_result"]["percentage"] = float(match.group(1))
                    logger.info(f"Found percentage: {match.group(1)}")
                    break
        
        # Extract issue date if missing
        if not data["issue_details"]["date"]:
            date_patterns = [
                r'Date of Issue[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'Issue Date[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'Dated[:\s]+(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*(?i:Date|Dated)',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    date = match.group(1)
                    date = re.sub(r'[/]', '-', date)
                    data["issue_details"]["date"] = date
                    logger.info(f"Found issue date: {date}")
                    break
        
        # Extract place if missing
        if not data["issue_details"]["place"]:
            place_patterns = [
                r'Place[:\s]+([A-Za-z\s]+)',
                r'Issued at[:\s]+([A-Za-z\s]+)',
                r'Place of Issue[:\s]+([A-Za-z\s]+)',
            ]
            
            for pattern in place_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["issue_details"]["place"] = match.group(1).strip()
                    logger.info(f"Found issue place: {match.group(1)}")
                    break
        
        return data
    
    async def _add_confidence_scores(
        self, 
        structured_data: Dict[str, Any], 
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("Adding confidence scores")
        result = {}
        
        # Add confidence to candidate details
        result["candidate_details"] = {}
        for field, value in structured_data.get("candidate_details", {}).items():
            result["candidate_details"][field] = {
                "value": value,
                "confidence": await calculate_confidence(
                    field, 
                    value, 
                    ocr_result
                )
            }
        
        # Add confidence to subjects
        result["subjects"] = []
        for subject in structured_data.get("subjects", []):
            subject_with_confidence = {}
            for field, value in subject.items():
                if field != "subject":
                    subject_with_confidence[field] = value
            
            subject_with_confidence["confidence"] = await calculate_confidence(
                "subject", 
                subject.get("subject", ""),
                ocr_result,
                additional_data=subject_with_confidence
            )
            subject_with_confidence["subject"] = subject.get("subject", "")
            
            result["subjects"].append(subject_with_confidence)
        
        # Add confidence to overall result
        result["overall_result"] = {}
        for field, value in structured_data.get("overall_result", {}).items():
            result["overall_result"][field] = {
                "value": value,
                "confidence": await calculate_confidence(
                    field, 
                    value, 
                    ocr_result
                )
            }
        
        # Add confidence to issue details
        result["issue_details"] = {}
        for field, value in structured_data.get("issue_details", {}).items():
            result["issue_details"][field] = {
                "value": value,
                "confidence": await calculate_confidence(
                    field, 
                    value, 
                    ocr_result
                )
            }
        
        return result
    
    def _validate_and_clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Validating and cleaning data")
        
        # Filter out subjects with empty or None subject names
        valid_subjects = []
        for subject in data.get("subjects", []):
            if subject.get("subject"):
                valid_subjects.append(subject)
        
        # Replace subjects with valid ones
        data["subjects"] = valid_subjects
        
        # Ensure all required fields have proper structure
        for field in ["candidate_details", "overall_result", "issue_details"]:
            if field not in data:
                data[field] = {}
        
        return data
    
    def _convert_to_response_model(self, data: Dict[str, Any]) -> ExtractionResponse:
        return ExtractionResponse(
            candidate_details=CandidateDetails(**data["candidate_details"]),
            subjects=[SubjectMarks(**subject) for subject in data["subjects"]],
            overall_result=OverallResult(**data["overall_result"]),
            issue_details=IssueDetails(**data["issue_details"])
        )