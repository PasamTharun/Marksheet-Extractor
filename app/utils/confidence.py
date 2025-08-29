import re
from rapidfuzz import fuzz
from typing import Dict, Any, Optional, List
import numpy as np
import asyncio
from app.core.exceptions import MarksheetExtractionException

async def calculate_confidence(
    field_name: str, 
    field_value: str, 
    ocr_result: Dict[str, Any],
    additional_data: Optional[Dict[str, Any]] = None
) -> float:
    if not field_value:
        return 0.0
    
    validation_confidence = await _validate_field(field_name, field_value)
    ocr_confidence = await _get_ocr_confidence(field_value, ocr_result)
    context_confidence = await _get_context_confidence(
        field_name, 
        field_value, 
        ocr_result["text"],
        additional_data
    )
    
    weights = {
        "validation": 0.4,
        "ocr": 0.3,
        "context": 0.3
    }
    
    combined_confidence = (
        validation_confidence * weights["validation"] +
        ocr_confidence * weights["ocr"] +
        context_confidence * weights["context"]
    )
    
    return max(0.0, min(1.0, combined_confidence))

async def _validate_field(field_name: str, field_value: str) -> float:
    if not field_value:
        return 0.0
    
    if field_name == "name":
        if re.match(r'^[A-Za-z\s\-\.\']+$', field_value):
            words = field_value.split()
            if len(words) >= 2 and all(word[0].isupper() for word in words if word):
                return 0.95
            return 0.8
        return 0.3
    
    elif field_name == "father_name":
        return await _validate_field("name", field_value)
    
    elif field_name == "dob":
        if re.match(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}$', field_value):
            try:
                parts = re.split(r'[-/]', field_value)
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    return 0.95
            except (ValueError, IndexError):
                pass
        return 0.2
    
    elif field_name in ["roll_no", "registration_no"]:
        if re.match(r'^[A-Za-z0-9\-\/]+$', field_value):
            return 0.9
        return 0.5
    
    elif field_name == "exam_year":
        if re.match(r'^(19|20)\d{2}$', field_value):
            year = int(field_value)
            if 1980 <= year <= 2100:
                return 0.95
        return 0.3
    
    elif field_name == "board":
        if re.match(r'^[A-Za-z\s\&\-]+$', field_value) and field_value[0].isupper():
            return 0.9
        return 0.5
    
    elif field_name == "institution":
        if re.match(r'^[A-Za-z\s\&\-\.]+$', field_value) and field_value[0].isupper():
            return 0.9
        return 0.5
    
    elif field_name == "subject":
        if re.match(r'^[A-Za-z0-9\s\(\)\-\&]+$', field_value) and field_value[0].isupper():
            return 0.9
        return 0.5
    
    elif field_name in ["max_marks", "obtained_marks"]:
        try:
            marks = float(field_value)
            if 0 <= marks <= 1000:
                return 0.95
            return 0.7
        except (ValueError, TypeError):
            return 0.1
    
    elif field_name == "grade":
        if re.match(r'^[A-F][\+\-]?$|^First|Second|Third|Pass|Fail$', field_value):
            return 0.9
        return 0.4
    
    elif field_name == "division":
        if re.match(r'^First|Second|Third|Distinction|Pass|Fail$', field_value):
            return 0.95
        return 0.3
    
    elif field_name == "percentage":
        try:
            percentage = float(field_value)
            if 0 <= percentage <= 100:
                return 0.95
            return 0.5
        except (ValueError, TypeError):
            return 0.1
    
    elif field_name == "date":
        if re.match(r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}$', field_value):
            try:
                parts = re.split(r'[-/]', field_value)
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    return 0.95
            except (ValueError, IndexError):
                pass
        return 0.2
    
    elif field_name == "place":
        if re.match(r'^[A-Za-z\s\-]+$', field_value) and field_value[0].isupper():
            return 0.9
        return 0.5
    
    return 0.7

async def _get_ocr_confidence(field_value: str, ocr_result: Dict[str, Any]) -> float:
    text = ocr_result["text"]
    
    if field_value not in text:
        return 0.5
    
    ocr_error_indicators = [
        r'[0-9]+[oO][0-9]+',
        r'[lI][0-9]+',
        r'[0-9]+[lI]',
        r'[A-Za-z]{2,}[0-9]{2,}',
    ]
    
    for pattern in ocr_error_indicators:
        if re.search(pattern, field_value):
            return 0.6
    
    occurrences = []
    start = 0
    while True:
        pos = text.find(field_value, start)
        if pos == -1:
            break
        occurrences.append(pos)
        start = pos + 1
    
    if occurrences:
        window_size = 50
        max_similarity = 0.0
        
        for pos in occurrences:
            start_pos = max(0, pos - window_size)
            end_pos = min(len(text), pos + len(field_value) + window_size)
            context = text[start_pos:end_pos]
            
            similarity = fuzz.token_sort_ratio(field_value, context) / 100.0
            max_similarity = max(max_similarity, similarity)
        
        if max_similarity > 0.9:
            return 0.9
        elif max_similarity > 0.7:
            return 0.8
        elif max_similarity > 0.5:
            return 0.7
    
    return 0.85

async def _get_context_confidence(
    field_name: str, 
    field_value: str, 
    ocr_text: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> float:
    occurrences = []
    start = 0
    while True:
        pos = ocr_text.find(field_value, start)
        if pos == -1:
            break
        occurrences.append(pos)
        start = pos + 1
    
    if not occurrences:
        return 0.3
    
    context_scores = []
    window_size = 150
    
    for pos in occurrences:
        start_pos = max(0, pos - window_size)
        end_pos = min(len(ocr_text), pos + len(field_value) + window_size)
        context = ocr_text[start_pos:end_pos].lower()
        
        indicators = _get_field_indicators(field_name)
        
        score = 0.0
        for indicator in indicators:
            if indicator in context:
                score = max(score, 0.8)
        
        if field_name == "name" and any(term in context for term in [
            'candidate', 'student', 'name of', 's/o', 'd/o', 'son of', 'daughter of'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "father_name" and any(term in context for term in [
            'father', 'mother', 'parent', 'guardian', 's/o', 'd/o'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "dob" and any(term in context for term in [
            'birth', 'dob', 'date of birth', 'born'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "roll_no" and any(term in context for term in [
            'roll', 'roll no', 'roll number', 'roll no.'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "registration_no" and any(term in context for term in [
            'reg', 'registration', 'reg no', 'reg. no'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "exam_year" and any(term in context for term in [
            'year', 'exam year', 'year of', 'academic year'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "board" and any(term in context for term in [
            'board', 'university', 'council', 'authority'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "institution" and any(term in context for term in [
            'school', 'college', 'institution', 'academy', 'vidyalaya'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "subject" and any(term in context for term in [
            'subject', 'paper', 'course', 'discipline'
        ]):
            score = max(score, 0.9)
        
        elif field_name in ["max_marks", "obtained_marks"] and any(term in context for term in [
            'marks', 'score', 'points', 'maximum', 'obtained', 'secured'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "grade" and any(term in context for term in [
            'grade', 'grading', 'result'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "division" and any(term in context for term in [
            'division', 'class', 'distinction', 'category'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "percentage" and any(term in context for term in [
            'percentage', 'percent', '%', 'aggregate'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "date" and any(term in context for term in [
            'date', 'issue date', 'dated', 'date of issue'
        ]):
            score = max(score, 0.9)
        
        elif field_name == "place" and any(term in context for term in [
            'place', 'issued at', 'place of issue', 'location'
        ]):
            score = max(score, 0.9)
        
        if score == 0.0:
            score = 0.5
        
        context_scores.append(score)
    
    return max(context_scores)

def _get_field_indicators(field_name: str) -> List[str]:
    indicators = {
        "name": ["name", "candidate", "student", "name of"],
        "father_name": ["father", "mother", "parent", "guardian", "s/o", "d/o"],
        "dob": ["birth", "dob", "date of birth", "born"],
        "roll_no": ["roll", "roll no", "roll number", "roll no."],
        "registration_no": ["reg", "registration", "reg no", "reg. no"],
        "exam_year": ["year", "exam year", "year of", "academic year"],
        "board": ["board", "university", "council", "authority"],
        "institution": ["school", "college", "institution", "academy", "vidyalaya"],
        "subject": ["subject", "paper", "course", "discipline"],
        "max_marks": ["max", "maximum", "total", "out of"],
        "obtained_marks": ["obtained", "scored", "secured", "marks"],
        "grade": ["grade", "grading", "result"],
        "division": ["division", "class", "distinction", "category"],
        "percentage": ["percentage", "percent", "%", "aggregate"],
        "date": ["date", "issue date", "dated", "date of issue"],
        "place": ["place", "issued at", "place of issue", "location"]
    }
    
    return indicators.get(field_name, [])