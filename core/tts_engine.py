# -*- coding: utf-8 -*-
"""
TTS 합성을 담당하는 공용 코드.

목소리 ID 하나만 넘기면, core/tts_voices.py에 적힌 engine 값을 보고 무료
edge-tts로 만들지 유료 AWS Polly로 만들지 알아서 골라서 mp3 오디오 바이트를
돌려준다. web/app.py(미리듣기 버튼)와 cogs/tts.py(실제 음성채널 재생)가 둘 다
이 모듈의 synthesize()만 부르면 되게 만들어서, 엔진을 하나 더 늘려도 이 파일만
고치면 되게 했다.

AWS Polly는 boto3(동기 라이브러리)라서, 봇의 이벤트 루프를 막지 않도록
run_in_executor로 별도 스레드에서 돌린다.
"""
from __future__ import annotations

import asyncio
import os

import edge_tts

from core.tts_voices import TTS_VOICES

_VOICE_LOOKUP = {v["id"]: v for v in TTS_VOICES}
_polly_client = None


def _get_polly_client():
    global _polly_client
    if _polly_client is None:
        import boto3  # AWS를 안 쓰면 이 줄까지 올 일이 없어서, 여기서만 불러온다.

        _polly_client = boto3.client("polly", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
    return _polly_client


def _synthesize_polly_sync(text: str, voice_id: str, engine: str) -> bytes:
    client = _get_polly_client()
    response = client.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=voice_id, Engine=engine)
    return response["AudioStream"].read()


async def _synthesize_edge(text: str, voice_id: str) -> bytes:
    buf = bytearray()
    async for chunk in edge_tts.Communicate(text, voice_id).stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)


async def synthesize(text: str, voice_id: str) -> bytes:
    """목소리 ID 하나로 mp3 오디오 바이트를 만들어 돌려준다."""
    info = _VOICE_LOOKUP.get(voice_id)

    if info and info.get("engine") == "polly":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _synthesize_polly_sync, text, info["polly_voice_id"], info.get("polly_engine", "neural")
        )

    return await _synthesize_edge(text, voice_id)
