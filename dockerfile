# بەکارهێنانی Python 3.10
FROM python:3.10-slim

# ڕێگەدان بە پاکێجەکان
ENV DEBIAN_FRONTEND=noninteractive

# دامەزراندنی FFmpeg و پێداویستییەکان
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# گۆڕینی ڕێڕەوی کار
WORKDIR /app

# کۆپی کردنی فایلەکان
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# فەرمانی دەستپێکردن
CMD ["python", "main.py"]
