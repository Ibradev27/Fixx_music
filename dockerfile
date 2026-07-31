# ─── بنەمای Python ──────────────────────────────────────
FROM python:3.10-slim

# ─── گۆڕینی کاردەکە بۆ /app ──────────────────────────
WORKDIR /app

# ─── دامەزراندنی FFmpeg و پێداویستییەکان ──────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ─── کۆپی کردنی فایلەکانی پڕۆژە ──────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY .env.example .env  # ئەگەر هەیە

# ─── فەرمانی دەستپێکردن ──────────────────────────────
CMD ["python", "main.py"]
