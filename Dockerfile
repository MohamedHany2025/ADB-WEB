FROM python:3.9-slim

WORKDIR /app

# Copy files
COPY requirements.txt .
COPY server.py .
COPY templates/ templates/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment
ENV FLASK_ENV=production
ENV DEBUG=False

# Expose port
EXPOSE 8000

# Run
CMD ["python", "server.py"]
