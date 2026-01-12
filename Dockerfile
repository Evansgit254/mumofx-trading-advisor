# Use official lightweight Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set work directory
WORKDIR /app

# Install system dependencies (required for some python packages like talib or build tools if needed)
# Added gcc and python3-dev for potential compilation needs
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . .

# Create directory for database/logs to ensure volume mounting works correctly
RUN mkdir -p database logs outputs

# Create non-root user for security
RUN useradd -m trader && chown -R trader:trader /app
USER trader

# Run the application
CMD ["python", "main.py"]
