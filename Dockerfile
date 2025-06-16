FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements-simplified.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "app:app"] 