import os
import fitz  # PyMuPDF
import cv2
import pytesseract
from PIL import Image
import io
import asyncio
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from app.core.config import settings
from app.core.exceptions import MarksheetExtractionException
import logging

logger = logging.getLogger(__name__)

class OCRService:
    """
    Service for extracting text from images and PDFs using OCR
    """
    def __init__(self):
        # Set Tesseract path if provided
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            logger.info(f"Using Tesseract from: {settings.TESSERACT_PATH}")
    
    async def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from a file (image or PDF)
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict: Extracted text and metadata
        """
        try:
            logger.info(f"Starting text extraction for file: {file_path}")
            logger.info(f"File exists: {os.path.exists(file_path)}")
            
            if os.path.exists(file_path):
                logger.info(f"File size: {os.path.getsize(file_path)} bytes")
            
            # Determine file type
            file_extension = os.path.splitext(file_path)[1].lower()
            logger.info(f"File extension: {file_extension}")
            
            if file_extension == ".pdf":
                logger.info("Processing as PDF file")
                return await self._extract_from_pdf(file_path)
            elif file_extension in [".jpg", ".jpeg", ".png", ".webp"]:
                logger.info("Processing as image file")
                return await self._extract_from_image(file_path)
            else:
                logger.error(f"Unsupported file type: {file_extension}")
                raise MarksheetExtractionException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_extension}"
                )
                
        except Exception as e:
            logger.error(f"Error during text extraction: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise MarksheetExtractionException(
                status_code=500,
                detail=f"Error during text extraction: {str(e)}"
            )
    
    async def _extract_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from a PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict: Extracted text and metadata
        """
        logger.info("Extracting text from PDF")
        
        # Open the PDF
        pdf_document = fitz.open(file_path)
        logger.info(f"PDF opened successfully. Pages: {len(pdf_document)}")
        
        # Extract text from each page
        text_by_page = []
        images = []
        
        for page_num in range(len(pdf_document)):
            logger.info(f"Processing page {page_num + 1}")
            page = pdf_document[page_num]
            
            # Extract text
            text = page.get_text()
            logger.info(f"Page {page_num + 1} text length: {len(text)}")
            if text.strip():
                text_by_page.append(text)
            
            # Extract images
            image_list = page.get_images(full=True)
            logger.info(f"Page {page_num + 1} has {len(image_list)} images")
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Convert to PIL Image
                image = Image.open(io.BytesIO(image_bytes))
                images.append({
                    "page": page_num,
                    "index": img_index,
                    "image": image
                })
        
        # Combine all text
        full_text = "\n".join(text_by_page)
        logger.info(f"Total extracted text length: {len(full_text)}")
        
        # If no text was found, try OCR on images
        if not full_text.strip() and images:
            logger.info("No text found, attempting OCR on extracted images")
            ocr_results = []
            for img_data in images:
                ocr_text = await self._ocr_image(img_data["image"])
                if ocr_text.strip():
                    ocr_results.append(f"Page {img_data['page'] + 1}, Image {img_data['index'] + 1}:\n{ocr_text}")
            
            full_text = "\n\n".join(ocr_results)
            logger.info(f"OCR from images extracted {len(full_text)} characters")
        
        return {
            "text": full_text,
            "metadata": {
                "type": "pdf",
                "pages": len(pdf_document),
                "images_extracted": len(images)
            }
        }
    
    async def _extract_from_image(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from an image file
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dict: Extracted text and metadata
        """
        logger.info("Extracting text from image")
        
        # Load image
        try:
            image = Image.open(file_path)
            logger.info(f"Image loaded successfully. Format: {image.format}, Size: {image.size}, Mode: {image.mode}")
        except Exception as e:
            logger.error(f"Failed to load image: {str(e)}")
            raise MarksheetExtractionException(
                status_code=500,
                detail=f"Failed to load image: {str(e)}"
            )
        
        # Convert WebP to JPEG if needed for better OCR compatibility
        if image.format == "WEBP":
            logger.info("Converting WebP to JPEG")
            # Convert to RGB mode (removes alpha channel if present)
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                image = background
            else:
                image = image.convert("RGB")
        
        # Try multiple preprocessing methods
        methods = [
            ("standard", self._preprocess_image_standard),
            ("adaptive", self._preprocess_image_adaptive),
            ("otsu", self._preprocess_image_otsu),
        ]
        
        best_text = ""
        best_confidence = 0
        
        for method_name, preprocess_func in methods:
            logger.info(f"Trying preprocessing method: {method_name}")
            try:
                # Preprocess image
                preprocessed_image = await preprocess_func(image)
                
                # Extract text using OCR
                text = await self._ocr_image(preprocessed_image)
                logger.info(f"Method {method_name} extracted {len(text)} characters")
                
                # Calculate confidence
                if text.strip():
                    confidence = self._calculate_ocr_confidence(text)
                    logger.info(f"Method {method_name} confidence: {confidence}")
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_text = text
            except Exception as e:
                logger.warning(f"Method {method_name} failed: {str(e)}")
                continue
        
        logger.info(f"Best OCR result: {len(best_text)} characters with confidence {best_confidence}")
        
        return {
            "text": best_text,
            "metadata": {
                "type": "image",
                "format": image.format,
                "size": image.size,
                "mode": image.mode,
                "ocr_confidence": best_confidence
            }
        }
    
    async def _preprocess_image_standard(self, image: Image.Image) -> Image.Image:
        """Standard preprocessing method"""
        logger.info("Using standard preprocessing")
        
        # Convert to OpenCV format
        open_cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Convert back to PIL Image
        return Image.fromarray(thresh)
    
    async def _preprocess_image_adaptive(self, image: Image.Image) -> Image.Image:
        """Adaptive preprocessing with denoising"""
        logger.info("Using adaptive preprocessing with denoising")
        
        # Convert to OpenCV format
        open_cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Convert back to PIL Image
        return Image.fromarray(processed)
    
    async def _preprocess_image_otsu(self, image: Image.Image) -> Image.Image:
        """Otsu thresholding preprocessing"""
        logger.info("Using Otsu thresholding preprocessing")
        
        # Convert to OpenCV format
        open_cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply Otsu's thresholding
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Convert back to PIL Image
        return Image.fromarray(thresh)
    
    async def _ocr_image(self, image: Image.Image) -> str:
        """
        Perform OCR on an image
        
        Args:
            image: PIL Image to perform OCR on
            
        Returns:
            str: Extracted text
        """
        logger.info("Performing OCR on image")
        
        # Try multiple PSM modes for better results
        psm_modes = [
            (6, "Assume a single uniform block of text"),
            (3, "Fully automatic page segmentation, but no OSD"),
            (4, "Assume a single column of text of variable sizes"),
            (11, "Sparse text. Find as much text as possible in no particular order"),
            (12, "Sparse text with OSD"),
            (1, "Automatic page segmentation with OSD"),
        ]
        
        best_text = ""
        best_confidence = 0
        
        for psm, description in psm_modes:
            try:
                logger.info(f"Trying PSM {psm}: {description}")
                
                # Use Tesseract to extract text with confidence data
                data = pytesseract.image_to_data(
                    image,
                    lang='eng',
                    config=f'--oem 3 --psm {psm}',
                    output_type=pytesseract.Output.DICT
                )
                
                # Calculate average confidence
                confidences = [int(c) for c in data['conf'] if int(c) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # Get text
                text = ' '.join([t for t in data['text'] if t.strip()])
                
                logger.info(f"PSM {psm}: {len(text)} characters, avg confidence: {avg_confidence}")
                
                if avg_confidence > best_confidence:
                    best_confidence = avg_confidence
                    best_text = text
                    
            except Exception as e:
                logger.warning(f"PSM {psm} failed: {str(e)}")
                continue
        
        logger.info(f"Best OCR result: {len(best_text)} characters with confidence {best_confidence}")
        return best_text
    
    def _calculate_ocr_confidence(self, text: str) -> float:
        """Calculate a confidence score for OCR text"""
        if not text.strip():
            return 0.0
        
        # Factors that increase confidence:
        # 1. Length of text
        # 2. Presence of alphanumeric characters
        # 3. Presence of common words
        
        score = 0.0
        
        # Length factor (up to 40 points)
        length_factor = min(len(text) / 100, 1.0) * 40
        score += length_factor
        
        # Alphanumeric ratio (up to 30 points)
        alnum_count = sum(c.isalnum() or c.isspace() for c in text)
        alnum_ratio = alnum_count / len(text) if text else 0
        score += alnum_ratio * 30
        
        # Common words factor (up to 30 points)
        common_words = ['name', 'roll', 'subject', 'marks', 'board', 'school', 'date', 'result']
        word_count = sum(1 for word in common_words if word.lower() in text.lower())
        score += min(word_count * 5, 30)
        
        return min(score, 100.0)