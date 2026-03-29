FROM mem0/mem0-api-server:latest

RUN pip install --no-cache-dir "psycopg[binary,pool]>=3.2.0"

RUN mkdir -p /app/history

COPY main.py /app/main.py
