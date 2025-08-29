FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a startup script
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'PORT=${PORT:-8000}' >> /app/start.sh && \
    echo 'exec uvicorn app.main:app --host 0.0.0.0 --port $PORT' >> /app/start.sh && \
    chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Run the startup script
CMD ["/app/start.sh"]