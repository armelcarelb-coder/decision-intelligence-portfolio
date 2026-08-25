FROM mcr.microsoft.com/devcontainers/python:3.12

# =====================================================
# SYSTEM PACKAGES
# =====================================================

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    git \
    chromium \
    chromium-driver \
    xvfb \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2t64 \
    libgbm1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# =====================================================
# PYTHON
# =====================================================

RUN pip install --upgrade pip

# =====================================================
# ENV
# =====================================================

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER=/usr/bin/chromedriver