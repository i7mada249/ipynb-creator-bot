FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
COPY *.ttf .
COPY bot.py .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
#RUN pip install --upgrade pip ipython ipykernel
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*


CMD ["python", "bot.py"]