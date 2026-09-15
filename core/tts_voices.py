# -*- coding: utf-8 -*-
"""
TTS에서 고를 수 있는 목소리 목록. web/app.py(설정 페이지의 드롭다운/미리듣기)와
cogs/tts.py(/목소리설정 명령어, 실제 재생)가 같은 목록을 쓰도록 여기 하나로 모아뒀다.

engine이 "edge"면 무료(edge-tts, 마이크로소프트), "polly"면 AWS Polly(유료,
.env에 AWS 키가 있어야 동작)다. 실제로 어느 쪽으로 합성할지는 core/tts_engine.py가
이 목록의 engine 값을 보고 정한다.

마이크로소프트 엣지 TTS 목소리 중, 한국어 전용 목소리 외에 "다국어(Multilingual)"
목소리도 넣어뒀다 — 원래 언어가 한국어가 아니어도 한국어 텍스트를 실제로 읽을 수
있는 걸 확인했다(edge_tts.list_voices()로 확인 + 직접 합성 테스트 통과).
새 목소리가 마이크로소프트 쪽에 추가되면 여기 목록도 같이 늘려주면 된다.

AWS Polly는 한국어(ko-KR) 목소리가 "서연(Seoyeon)" 하나뿐이다 (2026년 기준).
id는 "polly:VoiceId:엔진" 형태의 조합 문자열로 만들어서, 같은 목소리를 다른
엔진(neural/generative)으로 여러 개 등록해도 서로 안 겹치게 했다.
"""
from __future__ import annotations

import os

DEFAULT_VOICE = "ko-KR-SunHiNeural"

TTS_VOICES = [
    {"id": "ko-KR-SunHiNeural", "label": "선히 (여성)", "engine": "edge"},
    {"id": "ko-KR-InJoonNeural", "label": "인준 (남성)", "engine": "edge"},
    {"id": "ko-KR-HyunsuMultilingualNeural", "label": "현수 (남성, 다국어)", "engine": "edge"},
    {"id": "en-US-AvaMultilingualNeural", "label": "에이바 (여성, 다국어)", "engine": "edge"},
    {"id": "en-US-AndrewMultilingualNeural", "label": "앤드류 (남성, 다국어)", "engine": "edge"},
    {"id": "en-US-BrianMultilingualNeural", "label": "브라이언 (남성, 다국어)", "engine": "edge"},
    {"id": "en-US-EmmaMultilingualNeural", "label": "엠마 (여성, 다국어)", "engine": "edge"},
    {"id": "en-AU-WilliamMultilingualNeural", "label": "윌리엄 (남성, 다국어)", "engine": "edge"},
    {"id": "fr-FR-VivienneMultilingualNeural", "label": "비비엔 (여성, 다국어)", "engine": "edge"},
    {"id": "fr-FR-RemyMultilingualNeural", "label": "레미 (남성, 다국어)", "engine": "edge"},
    {"id": "de-DE-SeraphinaMultilingualNeural", "label": "세라피나 (여성, 다국어)", "engine": "edge"},
    {"id": "de-DE-FlorianMultilingualNeural", "label": "플로리안 (남성, 다국어)", "engine": "edge"},
    {"id": "it-IT-GiuseppeMultilingualNeural", "label": "주세페 (남성, 다국어)", "engine": "edge"},
    {"id": "pt-BR-ThalitaMultilingualNeural", "label": "탈리타 (여성, 다국어)", "engine": "edge"},
    {
        "id": "polly:Seoyeon:neural",
        "label": "서연 (여성, AWS Polly Neural · 유료 — .env에 AWS 키 필요)",
        "engine": "polly",
        "polly_voice_id": "Seoyeon",
        "polly_engine": "neural",
    },
]


def available_voices() -> list[dict]:
    """화면(설정 페이지, /목소리설정)에 실제로 보여줄 목소리 목록.

    .env에 AWS 키가 없으면 Polly 목소리는 목록에서 숨긴다 — 그냥 놔두면 골라도
    항상 실패하기만 해서 혼란스럽기 때문. 키를 넣고 봇/설정 페이지를 재시작하면
    바로 목록에 나타난다.
    """
    has_aws = bool(os.getenv("AWS_ACCESS_KEY_ID"))
    return [v for v in TTS_VOICES if v.get("engine") != "polly" or has_aws]
