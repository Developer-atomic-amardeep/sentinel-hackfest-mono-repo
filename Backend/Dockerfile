# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
# Install dependencies from pyproject.toml system-wide
RUN uv pip install --system --no-cache \
    "fastapi>=0.121.2" \
    "langgraph>=1.0.3" \
    "openai>=1.58.1" \
    "pydantic[email]>=2.12.4" \
    "python-dotenv>=1.0.0" \
    "python-multipart>=0.0.20" \
    "uvicorn>=0.38.0" \
    "PyPDF2" \
    "python-docx" \
    "agora-token-builder"

# Copy the rest of the application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose the port the app runs on
EXPOSE 9000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the application
CMD ["python", "main.py"]

