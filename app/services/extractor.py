import os
import json
import re
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
        try:
            logger.info(f"Starting extraction for file: {file_path}")
            
            ocr_result = await self.ocr_service.extract_text(file_path)
            logger.debug(f"OCR extracted text: {ocr_result['text'][:500]}...")
            
            structured_data = await self.llm_service.extract_structured_data(
                ocr_result["text"], 
                ocr_result.get("metadata", {})
            )
            logger.debug(f"LLM structured data: {structured_data}")
            
            if not structured_data.get("subjects"):
                logger.warning("LLM didn't extract subjects, using fallback method")
                structured_data["subjects"] = self._extract_subjects_fallback(ocr_result["text"])
                logger.debug(f"Fallback subjects: {structured_data['subjects']}")
            
            structured_data = self._post_process_missing_fields(structured_data, ocr_result["text"])
            
            result_with_confidence = await self._add_confidence_scores(
                structured_data, 
                ocr_result
            )
            
            validated_data = self._validate_and_clean_data(result_with_confidence)
            
            logger.info("Extraction completed successfully")
            return validated_data
            
        except Exception as e:
            logger.error(f"Error during extraction: {str(e)}")
            raise MarksheetExtractionException(
                status_code=500, 
                detail=f"Error during extraction: {str(e)}"
            )
    
    def _extract_subjects_fallback(self, ocr_text: str) -> List[Dict[str, Any]]:
        subjects = []
        
        table_patterns = [
            r'([A-Za-z\s&]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([A-Za-z0-9+-]*)',
            r'([A-Za-z\s&]+)\s+(\d+)\s+(\d+)\s+([A-Za-z0-9+-]*)',
            r'([A-Za-z\s&]+):\s*(\d+)\s*/\s*(\d+)',
            r'([A-Za-z\s&]+)\s*-\s*(\d+)',
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, ocr_text, re.IGNORECASE)
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
        
        lines = ocr_text.split('\n')
        for line in lines:
            subject_match = re.search(r'([A-Za-z\s&]{3,})\s*[:\-]?\s*(\d+)', line)
            if subject_match:
                subject_name = subject_match.group(1).strip()
                marks = subject_match.group(2).strip()
                
                if self._is_valid_subject(subject_name):
                    subjects.append({
                        "subject": subject_name,
                        "max_marks": None,
                        "obtained_marks": int(marks) if marks.isdigit() else None,
                        "grade": None
                    })
        
        return subjects
    
    def _is_valid_subject(self, subject_name: str) -> bool:
        exclude_terms = [
            'total', 'grand total', 'result', 'division', 'percentage',
            'grade', 'marks', 'obtained', 'maximum', 'subject', 'name',
            'roll', 'registration', 'board', 'school', 'college'
        ]
        
        subject_lower = subject_name.lower()
        
        if any(term in subject_lower for term in exclude_terms):
            return False
        
        if len(subject_name) < 3 or not subject_name[0].isalpha():
            return False
        
        letter_ratio = sum(c.isalpha() for c in subject_name) / len(subject_name)
        return letter_ratio > 0.5
    
    def _post_process_missing_fields(self, data: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
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
                    break
        
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
                    break
        
        if not data["overall_result"]["percentage"]:
            percentage_patterns = [
                r'Percentage[:\s]+(\d+(?:\.\d+)?)%',
                r'(\d+(?:\.\d+)?)%\s*(?i:Percentage|Percent)',
                r'Overall[:\s]+(\d+(?:\.\d+)?)%',
                r'Total Percentage[:\s]+(\d+(?:\.\d+)?)%',
            ]
            
            for pattern in percentage_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["overall_result"]["percentage"] = float(match.group(1))
                    break
        
        if not data["overall_result"]["grade"]:
            grade_patterns = [
                r'Grade[:\s]+([A-F][\+\-]?)',
                r'Overall Grade[:\s]+([A-F][\+\-]?)',
                r'Final Grade[:\s]+([A-F][\+\-]?)',
            ]
            
            for pattern in grade_patterns:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    data["overall_result"]["grade"] = match.group(1).strip()
                    break
        
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
                    break
        
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
                    break
        
        return data
    
    async def _add_confidence_scores(
        self, 
        structured_data: Dict[str, Any], 
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = {}
        
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
        valid_subjects = []
        for subject in data.get("subjects", []):
            if subject.get("subject"):
                valid_subjects.append(subject)
        
        data["subjects"] = valid_subjects
        
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