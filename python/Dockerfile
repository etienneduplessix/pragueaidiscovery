FROM python:3.9-slim

# Set working directory
WORKDIR /app


# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ./app/ .

# Create temporary directory for PDF files
RUN mkdir -p /tmp

# Set Python path
ENV PYTHONPATH=/app

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]