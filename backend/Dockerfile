FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU uniquement (léger ~300MB vs 2GB+ CUDA)
RUN pip install --no-cache-dir --timeout=300 \
    torch==2.3.1+cpu torchvision==0.18.1+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# EasyOCR (dépend de torch)
RUN pip install --no-cache-dir --timeout=300 easyocr==1.7.1

# Reste des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Pré-télécharger les modèles EasyOCR (ar + fr)
RUN python -c "import easyocr; easyocr.Reader(['ar', 'fr'], gpu=False)" || true

COPY . .

EXPOSE 8000
