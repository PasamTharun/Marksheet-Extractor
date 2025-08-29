import os
import json
import re
import traceback
from typing import Dict, Any, List, Optional
import asyncio
import google.generativeai as genai
import logging
from app.core.config import settings
from app.core.exceptions import MarksheetExtractionException

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for using LLM (Gemini) to extract structured data from OCR text
    """
    def __init__(self):
        try:
            if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "yourapikey":
                logger.error("Gemini API key is not set properly")
                raise ValueError("Gemini API key is not set properly")
            
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model_names = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-pro",
            ]
            
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    logger.info(f"Gemini model initialized successfully with model: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to initialize model {model_name}: {str(e)}")
            
            if self.model is None:
                available_models = [m.name for m in genai.list_models()]
                logger.error(f"Available models: {available_models}")
                raise ValueError(f"None of the expected models are available. Available models: {available_models}")
                
        except Exception as e:
            logger.error(f"Error initializing Gemini model: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def extract_structured_data(
        self, 
        ocr_text: str, 
        metadata: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        try:
            logger.info("Starting LLM extraction")
            
            cleaned_text = self._clean_ocr_text(ocr_text)
            logger.info(f"Cleaned OCR text length: {len(cleaned_text)}")
            
            prompt = self._create_prompt(cleaned_text)
            logger.info("Created prompt for LLM")
            
            response = await self._generate_response(prompt)
            logger.info("Generated response from LLM")
            
            structured_data = self._parse_response(response)
            logger.info("Parsed LLM response")
            
            processed_data = self._post_process_data(structured_data)
            logger.info("Post-processed data")
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error during LLM extraction: {str(e)}")
            logger.error(traceback.format_exc())
            raise MarksheetExtractionException(
                status_code=500,
                detail=f"Error during LLM extraction: {str(e)}"
            )
    
    def _create_prompt(self, ocr_text: str) -> str:
        return f"""
        You are an expert at extracting structured information from marksheets of any format.
        I will provide you with text extracted from a marksheet using OCR.
        Your task is to extract the following information and return it as a JSON object.
        
        IMPORTANT: The marksheet can be from ANY board or institution with ANY layout.
        Be flexible in identifying fields. Look for:
        - Field labels (like "Name:", "Roll No:", "Subject", etc.)
        - Common patterns (like dates in DD-MM-YYYY or similar formats)
        - Tabular data for subjects (look for columns with marks/grades)
        - Positional information (like names at the top, results at the bottom)
        
        Extract these fields:
        
        1. Candidate details:
           - name: Full name of the candidate (look for "Name", "Candidate", "Student")
           - father_name: Father's or mother's name (look for "Father", "Mother", "Parent")
           - dob: Date of birth (look for "DOB", "Birth", "Date of Birth")
           - roll_no: Roll number (look for "Roll", "Roll No", "Roll Number")
           - registration_no: Registration number (look for "Reg", "Registration")
           - exam_year: Year of examination (look for "Year", "Exam Year")
           - board: Board or university name (look for "Board", "University")
           - institution: School or college name (look for "School", "College", "Institution")
               
        2. Subject-wise marks:
           Look for ANY tabular data or list of subjects with marks. Patterns to look for:
           - Subject names followed by numbers (marks/grades)
           - Columns with headers like "Subject", "Marks", "Grade", "Score"
           - Rows containing subject information
           - Lines like "Mathematics: 85", "Science A1", etc.
           
           Extract each subject as an object with:
           - subject: Name of the subject
           - max_marks: Maximum marks (if available)
           - obtained_marks: Marks obtained (if available)
           - grade: Grade (if available)
           
           If marks are presented as "Subject: 85/100", extract:
           - subject: "Subject", max_marks: 100, obtained_marks: 85, grade: null
               
        3. Overall result:
           - division: Division or class (look for "Division", "Class", "Result")
           - percentage: Overall percentage (look for "%", "Percentage")
           - grade: Overall grade (look for "Grade", "Result")
               
        4. Issue details:
           - date: Date of issue (look for "Date", "Issue Date")
           - place: Place of issue (look for "Place", "Issued at")
        
        Here is the extracted text from the marksheet:
        ---
        {ocr_text}
        ---
        
        Extract the information and return it as a JSON object with the following structure:
        ```json
        {{
            "candidate_details": {{
                "name": "...",
                "father_name": "...",
                "dob": "...",
                "roll_no": "...",
                "registration_no": "...",
                "exam_year": "...",
                "board": "...",
                "institution": "..."
            }},
            "subjects": [
                {{
                    "subject": "...",
                    "max_marks": ...,
                    "obtained_marks": ...,
                    "grade": "..."
                }},
                ...
            ],
            "overall_result": {{
                "division": "...",
                "percentage": "...",
                "grade": "..."
            }},
            "issue_details": {{
                "date": "...",
                "place": "..."
            }}
        }}
        ```
        
        If any information is not available, use null for that field.
        Be flexible with formats and layouts. The marksheet might not follow a standard pattern.
        Ensure the JSON is valid and properly formatted.
        """
    
    async def _generate_response(self, prompt: str) -> str:
        try:
            logger.info("Generating content from Gemini")
            response = self.model.generate_content(prompt)
            logger.info("Generated content successfully")
            return response.text
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            logger.error(traceback.format_exc())
            raise MarksheetExtractionException(
                status_code=500,
                detail=f"Error generating LLM response: {str(e)}"
            )
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        try:
            logger.info("Parsing LLM response")
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                logger.info("Found JSON in code block")
            else:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    logger.info("Found JSON directly in response")
                else:
                    logger.warning("No JSON found in response, returning empty structure")
                    return self._get_empty_structure()
            
            data = json.loads(json_str)
            logger.info("Successfully parsed JSON")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response as JSON: {str(e)}")
            logger.error(f"Response was: {response}")
            raise MarksheetExtractionException(
                status_code=500,
                detail=f"Error parsing LLM response as JSON: {str(e)}"
            )
    
    def _get_empty_structure(self) -> Dict[str, Any]:
        return {
            "candidate_details": {
                "name": None,
                "father_name": None,
                "dob": None,
                "roll_no": None,
                "registration_no": None,
                "exam_year": None,
                "board": None,
                "institution": None
            },
            "subjects": [],
            "overall_result": {
                "division": None,
                "percentage": None,
                "grade": None
            },
            "issue_details": {
                "date": None,
                "place": None
            }
        }
    
    def _clean_ocr_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\.\,\-\:\;\(\)\/\%\@\#\$\&\*\+\=\?\!\[\]\{\}\<\>\~\`\|\\]', '', text)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text
    
    def _post_process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Post-processing data")
        
        for field in data.get("candidate_details", {}):
            if data["candidate_details"][field]:
                data["candidate_details"][field] = self._clean_field_value(
                    data["candidate_details"][field]
                )
        
        for subject in data.get("subjects", []):
            for field in subject:
                if field in ["max_marks", "obtained_marks"] and subject[field]:
                    try:
                        subject[field] = float(subject[field])
                    except (ValueError, TypeError):
                        subject[field] = None
                elif field in ["grade", "subject"] and subject[field]:
                    subject[field] = self._clean_field_value(subject[field])
        
        for field in data.get("overall_result", {}):
            if data["overall_result"][field]:
                if field == "percentage":
                    try:
                        data["overall_result"][field] = float(data["overall_result"][field])
                    except (ValueError, TypeError):
                        data["overall_result"][field] = None
                else:
                    data["overall_result"][field] = self._clean_field_value(
                        data["overall_result"][field]
                    )
        
        for field in data.get("issue_details", {}):
            if data["issue_details"][field]:
                data["issue_details"][field] = self._clean_field_value(
                    data["issue_details"][field]
                )
        
        logger.info("Post-processing completed")
        return data
    
    def _clean_field_value(self, value: str) -> str:
        if not value:
            return value
        
        value = re.sub(r'\s+', ' ', value).strip()
        
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1].strip()
        
        return value