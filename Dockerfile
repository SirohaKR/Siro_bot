FROM python:3.11-slim

# 버퍼링 없이 즉시 stdout/stderr로 흘려보내서 `docker logs`에 바로 찍히게 함
ENV PYTHONUNBUFFERED=1

# TTS 오디오(mp3)를 디스코드 음성채널로 내보내려면 ffmpeg가 필요하다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
