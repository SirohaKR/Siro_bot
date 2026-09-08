FROM python:3.11-slim

# 버퍼링 없이 즉시 stdout/stderr로 흘려보내서 `docker logs`에 바로 찍히게 함
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
