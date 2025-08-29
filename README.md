

## 📄 Marksheet Extractor API

![Python](https://img.shields.io/badge/Python-3.9-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)
![Railway](https://img.shields.io/badge/Deployed%20on-Railway-purple.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

An AI-powered API that extracts structured data from marksheets using advanced OCR and Large Language Models. Supports multiple formats and boards with intelligent fallback mechanisms.

## ✨ Features

- 🖼️ **Multi-format Support**: Process JPG, PNG, WebP, and PDF files
- 🧠 **AI-Powered Extraction**: Leverages Google's Gemini LLM for intelligent data extraction
- 🔍 **Advanced OCR**: Uses Tesseract with multiple preprocessing methods for optimal text extraction
- 🎯 **Intelligent Fallbacks**: Robust pattern matching when AI extraction fails
- 📊 **Confidence Scoring**: Provides confidence scores for all extracted fields
- 🌐 **Board Agnostic**: Works with marksheets from any educational board
- 🚀 **Production Ready**: Deployed on Railway with automatic scaling

## 🛠️ Tech Stack

- **Backend**: Python 3.9, FastAPI
- **AI/ML**: Google Gemini API, Tesseract OCR
- **Image Processing**: OpenCV, Pillow
- **Deployment**: Railway, Docker
- **Testing**: Pytest, HTTPX

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Google Gemini API key
- Railway account (for deployment)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/marksheet-extractor.git
   cd marksheet-extractor
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Gemini API key
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run locally**
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`

## 📖 Usage

### API Endpoints

#### Extract Data from Single Marksheet

```bash
curl -X POST "https://your-app.railway.app/api/v1/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/marksheet.jpg"
```

#### Batch Extract Multiple Marksheets

```bash
curl -X POST "https://your-app.railway.app/api/v1/batch-extract" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@path/to/marksheet1.jpg" \
  -F "files=@path/to/marksheet2.pdf"
```

#### Health Check

```bash
curl "https://your-app.railway.app/health"
```

### Response Format

```json
{
  "candidate_details": {
    "name": { "value": "NARAYAN DEBNATH", "confidence": 0.875 },
    "father_name": { "value": "GOPINATH DEBNATH", "confidence": 0.62 },
    "dob": { "value": "01-01-2000", "confidence": 0.97 },
    "roll_no": { "value": "06937", "confidence": 0.885 },
    "registration_no": { "value": "REG123456", "confidence": 0.96 },
    "exam_year": { "value": "2007", "confidence": 0.785 },
    "board": { "value": "MADHYAMIK PARIKSHA", "confidence": 0.765 },
    "institution": { "value": "SIBPUR DINABANDHU INSTITUTION", "confidence": 0.725 }
  },
  "subjects": [
    {
      "subject": "Language",
      "max_marks": null,
      "obtained_marks": 156,
      "grade": null,
      "confidence": 0.95
    },
    {
      "subject": "Science",
      "max_marks": null,
      "obtained_marks": 214,
      "grade": null,
      "confidence": 0.92
    }
  ],
  "overall_result": {
    "division": { "value": "FIRST", "confidence": 0.645 },
    "percentage": { "value": null, "confidence": 0 },
    "grade": { "value": null, "confidence": 0 }
  },
  "issue_details": {
    "date": { "value": "31-05-2007", "confidence": 0.92 },
    "place": { "value": "Kolkata", "confidence": 0.92 }
  },
  "processing_time": 3.322,
  "file_type": "image/png",
  "file_size": 1469178
}
```
## Interface
<img width="994" height="906" alt="image" src="https://github.com/user-attachments/assets/a9d616e4-4db6-4d80-bfe1-80c2d5f65390" />


## 🚢 Deployment

### Railway Deployment

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize Project**
   ```bash
   railway init
   ```

4. **Set Environment Variables**
   In Railway dashboard, add:
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key
   ALLOWED_ORIGINS=["*"]
   MAX_FILE_SIZE=10485760
   ALLOWED_FILE_TYPES=["image/jpeg", "image/png", "image/webp", "application/pdf"]
   MAX_BATCH_SIZE=10
   TESSERACT_PATH=/usr/bin/tesseract
   TEMP_DIR=/tmp
   ```

5. **Deploy**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

### Docker Deployment

1. **Build Image**
   ```bash
   docker build -t marksheet-extractor .
   ```

2. **Run Container**
   ```bash
   docker run -p 8000:8000 \
    -e GEMINI_API_KEY=your_api_key \
    marksheet-extractor
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `ALLOWED_ORIGINS` | CORS allowed origins | `["*"]` |
| `MAX_FILE_SIZE` | Max upload size (bytes) | `10485760` |
| `ALLOWED_FILE_TYPES` | Supported file types | `["image/jpeg", "image/png", "image/webp", "application/pdf"]` |
| `MAX_BATCH_SIZE` | Max files in batch | `10` |
| `TESSERACT_PATH` | Path to Tesseract | `/usr/bin/tesseract` |
| `TEMP_DIR` | Temporary directory | `/tmp` |

## 🧪 Testing

Run the test suite:

```bash
pytest
```

Run specific test:

```bash
pytest app/tests/test_extractor.py
```

## 📊 Architecture

<img width="866" height="938" alt="image" src="https://github.com/user-attachments/assets/5c529e68-2ea4-45cd-9624-60be970174c4" />


## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

### Development Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## 🙏 Acknowledgments

- **Google Gemini** for providing the powerful LLM capabilities
- **Tesseract OCR** for robust text extraction
- **Railway** for seamless deployment
- **FastAPI** for the elegant web framework

<div align="center">
  Made with ❤️ by Pasam Tharun
</div>

