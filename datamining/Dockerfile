# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Ensure Python output is unbuffered so logs appear in real-time in Cloud Logging
ENV PYTHONUNBUFFERED=1

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Run extract_memories.py when the container launches
# Default to 500 emails but can be overridden by CMD arguments in Cloud Run Job
ENTRYPOINT ["python", "extract_memories.py"]
CMD ["500"]
