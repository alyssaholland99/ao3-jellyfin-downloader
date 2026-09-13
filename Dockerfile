# Use a lightweight Python base image compatible with Raspberry Pi (ARM)
FROM python:3.12-slim

# Install nmcli (NetworkManager) required for the WiFi fallback script
RUN apt-get update && apt-get install -y \
    network-manager \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY src/app.py .
COPY src/templates/ ./templates/

# Expose the Flask port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]