# -*- coding: utf-8 -*-
"""
TTS에서 고를 수 있는 목소리 목록. web/app.py(설정 페이지의 드롭다운/미리듣기)와
cogs/tts.py(/목소리설정 명령어)가 같은 목록을 쓰도록 여기 하나로 모아뒀다.

마이크로소프트 엣지 TTS 목소리 중, 한국어 전용 목소리 외에 "다국어(Multilingual)"
목소리도 넣어뒀다 — 원래 언어가 한국어가 아니어도 한국어 텍스트를 실제로 읽을 수
있는 걸 확인했다(edge_tts.list_voices()로 확인 + 직접 합성 테스트 통과).
새 목소리가 마이크로소프트 쪽에 추가되면 여기 목록도 같이 늘려주면 된다.
"""
from __future__ import annotations

DEFAULT_VOICE = "ko-KR-SunHiNeural"

TTS_VOICES = [
    {"id": "ko-KR-SunHiNeural", "label": "선히 (여성)"},
    {"id": "ko-KR-InJoonNeural", "label": "인준 (남성)"},
    {"id": "ko-KR-HyunsuMultilingualNeural", "label": "현수 (남성, 다국어)"},
    {"id": "en-US-AvaMultilingualNeural", "label": "에이바 (여성, 다국어)"},
    {"id": "en-US-AndrewMultilingualNeural", "label": "앤드류 (남성, 다국어)"},
    {"id": "en-US-BrianMultilingualNeural", "label": "브라이언 (남성, 다국어)"},
    {"id": "en-US-EmmaMultilingualNeural", "label": "엠마 (여성, 다국어)"},
    {"id": "en-AU-WilliamMultilingualNeural", "label": "윌리엄 (남성, 다국어)"},
    {"id": "fr-FR-VivienneMultilingualNeural", "label": "비비엔 (여성, 다국어)"},
    {"id": "fr-FR-RemyMultilingualNeural", "label": "레미 (남성, 다국어)"},
    {"id": "de-DE-SeraphinaMultilingualNeural", "label": "세라피나 (여성, 다국어)"},
    {"id": "de-DE-FlorianMultilingualNeural", "label": "플로리안 (남성, 다국어)"},
    {"id": "it-IT-GiuseppeMultilingualNeural", "label": "주세페 (남성, 다국어)"},
    {"id": "pt-BR-ThalitaMultilingualNeural", "label": "탈리타 (여성, 다국어)"},
]
