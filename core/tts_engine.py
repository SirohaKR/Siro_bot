# -*- coding: utf-8 -*-
"""
TTS 합성을 담당하는 공용 코드.

목소리 ID 하나만 넘기면, core/tts_voices.py에 적힌 engine 값을 보고 무료
edge-tts / 유료 AWS Polly / 유료 타입캐스트 중 알맞은 걸로 합성해서 mp3
오디오 바이트를 돌려준다. web/app.py(미리듣기 버튼)와 cogs/tts.py(실제
음성채널 재생)가 둘 다 이 모듈의 synthesize()만 부르면 되게 만들어서,
엔진을 하나 더 늘려도 이 파일만 고치면 되게 했다.

AWS Polly는 boto3(동기 라이브러리)라서, 봇의 이벤트 루프를 막지 않도록
run_in_executor로 별도 스레드에서 돌린다. 타입캐스트는 REST API라
discord.py가 이미 쓰고 있는 aiohttp로 바로 비동기 호출한다.
"""
from __future__ import annotations

import asyncio
import os

import aiohttp
import edge_tts

from core.chat_text import normalize_for_tts
from core.tts_voices import TTS_VOICES

_VOICE_LOOKUP = {v["id"]: v for v in TTS_VOICES}
_polly_client = None

_TYPECAST_API_BASE = "https://api.typecast.ai"
_typecast_voice_id_cache: dict[str, str] = {}


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


async def _resolve_typecast_voice_id(name: str) -> str:
    """"하준" 같은 한글 이름으로 실제 voice_id를 찾는다.

    voice_id를 코드에 직접 적어두지 않고 매번(첫 호출만) 타입캐스트 API로
    조회하는 이유: 타입캐스트 쪽에서 목소리를 개편하면 id가 바뀔 수 있는데,
    그럴 때 코드를 안 고쳐도 이름만 맞으면 계속 동작하게 하기 위해서다.
    """
    if name in _typecast_voice_id_cache:
        return _typecast_voice_id_cache[name]

    api_key = os.getenv("TYPECAST_API_KEY", "")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_TYPECAST_API_BASE}/v3/voices", headers={"X-API-KEY": api_key}
        ) as resp:
            resp.raise_for_status()
            voices = await resp.json()

    for voice in voices:
        if voice.get("voice_name", {}).get("kor") == name:
            _typecast_voice_id_cache[name] = voice["voice_id"]
            return voice["voice_id"]

    raise ValueError(f"타입캐스트에서 '{name}' 목소리를 찾지 못했어요.")


async def _synthesize_typecast(text: str, typecast_name: str) -> bytes:
    api_key = os.getenv("TYPECAST_API_KEY", "")
    voice_id = await _resolve_typecast_voice_id(typecast_name)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_TYPECAST_API_BASE}/v1/text-to-speech",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={
                "voice_id": voice_id,
                "text": text,
                "model": "ssfm-v30",
                "output": {"audio_format": "mp3"},
            },
        ) as resp:
            resp.raise_for_status()
            return await resp.read()


async def synthesize(text: str, voice_id: str) -> bytes:
    """목소리 ID 하나로 mp3 오디오 바이트를 만들어 돌려준다."""
    text = normalize_for_tts(text)
    info = _VOICE_LOOKUP.get(voice_id)

    if info and info.get("engine") == "polly":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _synthesize_polly_sync, text, info["polly_voice_id"], info.get("polly_engine", "neural")
        )

    if info and info.get("engine") == "typecast":
        return await _synthesize_typecast(text, info["typecast_name"])

    return await _synthesize_edge(text, voice_id)
