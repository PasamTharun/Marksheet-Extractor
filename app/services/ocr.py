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

class OCRService:
    """
    Service for extracting text from images and PDFs using OCR
    """
    def __init__(self):
        # Set Tesseract path if provided
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
    
    async def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from a file (image or PDF)
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict: Extracted text and metadata
        """
        try:
            # Determine file type
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == ".pdf":
                return await self._extract_from_pdf(file_path)
            elif file_extension in [".jpg", ".jpeg", ".png", ".webp"]:
                return await self._extract_from_image(file_path)
            else:
                raise MarksheetExtractionException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_extension}"
                )
                
        except Exception as e:
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
        # Open the PDF
        pdf_document = fitz.open(file_path)
        
        # Extract text from each page
        text_by_page = []
        images = []
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Extract text
            text = page.get_text()
            text_by_page.append(text)
            
            # Extract images
            image_list = page.get_images(full=True)
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
        
        # If no text was found, try OCR on images
        if not full_text.strip() and images:
            ocr_results = []
            for img_data in images:
                ocr_text = await self._ocr_image(img_data["image"])
                if ocr_text:
                    ocr_results.append(f"Page {img_data['page'] + 1}, Image {img_data['index'] + 1}:\n{ocr_text}")
            
            full_text = "\n\n".join(ocr_results)
        
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
        # Load image
        image = Image.open(file_path)
        
        # Convert WebP to JPEG if needed for better OCR compatibility
        if image.format == "WEBP":
            # Convert to RGB mode (removes alpha channel if present)
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                image = background
            else:
                image = image.convert("RGB")
        
        # Preprocess image
        preprocessed_image = await self._preprocess_image(image)
        
        # Extract text using OCR
        text = await self._ocr_image(preprocessed_image)
        
        return {
            "text": text,
            "metadata": {
                "type": "image",
                "format": image.format,
                "size": image.size,
                "mode": image.mode
            }
        }
    
    async def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results
        
        Args:
            image: PIL Image to preprocess
            
        Returns:
            Image: Preprocessed PIL Image
        """
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
    
    async def _ocr_image(self, image: Image.Image) -> str:
        """
        Perform OCR on an image
        
        Args:
            image: PIL Image to perform OCR on
            
        Returns:
            str: Extracted text
        """
        # Use Tesseract to extract text
        text = pytesseract.image_to_string(
            image,
            lang='eng',  # English language
            config='--oem 3 --psm 6'  # OEM 3: Default, PSM 6: Assume a single uniform block of text
        )
        
        return text