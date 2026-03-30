FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "mem0ai[graph]>=0.1.0" \
    "openai>=1.58.0" \
    "python-dotenv>=1.0.0" \
    "psycopg[binary,pool]>=3.2.0"

RUN mkdir -p /app/history

COPY main.py /app/main.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
