FROM python:3.12-slim

WORKDIR /app

# System libraries required by lxml and newspaper4k
RUN apt-get update && apt-get install -y \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer cache
# (only reinstalled when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 4040

ENTRYPOINT ["/entrypoint.sh"]
