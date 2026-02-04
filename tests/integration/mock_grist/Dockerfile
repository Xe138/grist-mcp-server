FROM python:3.14-slim@sha256:1a3c6dbfd2173971abba880c3cc2ec4643690901f6ad6742d0827bae6cefc925

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=8484
EXPOSE 8484

CMD ["python", "server.py"]
