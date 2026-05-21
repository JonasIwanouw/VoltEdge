# Tag Python 3.11 som base
FROM python:3.11-slim

# Sæt arbejdsmappen inde i containeren
WORKDIR /app

# Kopier requirements filen først
COPY requirements.txt .

# Installer alle Python pakker
RUN pip install --no-cache-dir -r requirements.txt

# Kopier resten af koden
COPY . .

# Åbn port 5000
EXPOSE 5000

# Start API'et
CMD ["python", "app.py"]
