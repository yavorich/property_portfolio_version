FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    LC_TIME=ru_RU.UTF-8

WORKDIR /backend/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget ca-certificates \
        libxrender1 libfontconfig1 libjpeg62-turbo \
        xfonts-75dpi xfonts-base \
        tesseract-ocr tesseract-ocr-eng \
    && wget -qO /tmp/wkhtmltox.deb \
        https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
    && rm /tmp/wkhtmltox.deb \
    && apt-get purge -y --auto-remove wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY backend .
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
