# -*- coding: utf-8 -*-
"""
타입캐스트 전체 목소리 카탈로그(2026년 기준 약 600개)를 가져오고 검색하는 코드.

core/tts_voices.py의 TTS_VOICES는 자주 쓸만한 것만 손으로 골라둔 "추천" 목록이고,
여기는 타입캐스트 API가 제공하는 전체 목소리를 그대로 가져와서 이름/성별/나이/
용도로 검색할 수 있게 해준다. "/목소리설정" 명령어의 자동완성과, 관리자 설정
페이지("🗣️ TTS")의 목소리 검색에서 함께 쓴다.

디스코드 슬래시 명령어의 선택지는 최대 25개까지만 보여줄 수 있어서, 600개를
전부 고정 목록으로 넣을 수는 없다. 그래서 사용자가 글자를 입력할 때마다 그
글자로 이 카탈로그를 검색해서 맞는 것만 최대 25개 보여주는 자동완성 방식을 쓴다.

한 번 받아온 목록은 과정(프로세스) 안에 계속 캐싱해둔다 — 타입캐스트가 목소리를
새로 추가하는 일이 잦지 않아서, 매번 API를 부르는 것보다 낫다. 새 목소리가
추가된 걸 반영하려면 봇/웹 페이지를 재시작하면 된다.

미리듣기는 타입캐스트가 목소리마다 미리 준비해둔 무료 샘플 음원(preview_url)을
그대로 쓴다 — 실제 합성 API(유료, 크레딧 소모)를 매번 부르지 않아도 된다.
"""
from __future__ import annotations

import os

import aiohttp

_TYPECAST_VOICES_URL = "https://api.typecast.ai/v3/voices"

_GENDER_KO = {"male": "남성", "female": "여성"}
_AGE_KO = {
    "child": "아동",
    "teenager": "청소년",
    "young_adult": "청년",
    "middle_age": "중년",
    "elder": "노년",
}

# 화면 필터에서 고를 수 있는 용도. API는 영어 값으로 주니, 필터 값은 영어 그대로 두고
# 보여주는 이름과 검색어(한글로 "애니메이션"이라고 쳐도 찾히게)만 한글로 붙인다.
USE_CASES_KO = {
    "Conversational": "대화",
    "Game": "게임",
    "Anime": "애니메이션",
    "Audiobook/Storytelling": "오디오북/이야기",
    "TikTok/Reels/Shorts": "쇼츠/릴스",
    "Ads/Promotion": "광고/홍보",
    "E-learning/Explainer": "교육/설명",
    "Radio/Podcast": "라디오/팟캐스트",
    "Documentary": "다큐",
    "Voicemail/Voice Assistant": "음성안내/비서",
    "Announcer": "아나운서",
    "News Reporter": "뉴스/기자",
    "Rapper": "랩",
}

_typecast_catalog_cache: list[dict] | None = None

# 영어 이름에 두 단어가 있어도 "캐스터/기자" 같은 직함이 붙은 한국 목소리는 남긴다.
_KOREAN_TITLES = ("캐스터", "기자", "아나운서", "앵커", "교수", "선생", "박사")
# 한국어 로마자에는 거의 안 쓰이는 글자(f, v, z, x)가 들어간 한 단어 이름은 대개
# 서양 이름이다 (Oliver, Jeff, Kevin...). 단, 신화 시리즈는 한국어 목소리라 예외.
_WESTERN_LETTERS = ("f", "v", "z", "x")
_MYTH_EXCEPTIONS = {"zeus", "valkyrie"}


def _looks_non_korean(names: dict) -> bool:
    """한국어권 목소리가 아닐 것 같은지 이름으로 추정한다.

    타입캐스트 API 응답에는 목소리의 언어를 나타내는 필드가 없고(목소리마다 여러 언어를
    읽을 수 있고, 언어는 합성 요청 때 정한다), 그래서 실제로 "한국어가 되는지"는 구분할
    수 없다. 대신 이름 모양으로 한국어권이 아닌 것 같은 것만 걸러내는 근사치다:
      1) 영어 이름이 "성 이름"처럼 두 단어 이상이면(예: "Miu Kobayashi") 대개 일본어권
         등이다 — 한국어 이름란도 발음을 한글로 옮겨 적은 것뿐이라("고바야시 미우")
         한국어 목소리라는 뜻이 아니다. 단 "캐스터/기자" 같은 직함이 붙은 건 남긴다.
      2) 한 단어여도 f/v/z/x가 들어간 서양식 이름(Oliver, Jeff, Kevin...)은 거른다.
    완벽하진 않아서(Lorenzo처럼 걸러지는 것도, Silas처럼 못 거르는 서양 이름도 있다),
    화면에서 "한국어권 목소리만" 체크를 풀면 전부 볼 수 있게 해뒀다.
    """
    eng_name = names.get("eng", "")
    kor_name = names.get("kor", "")
    if len(eng_name.split()) >= 2:
        return not any(title in kor_name for title in _KOREAN_TITLES)
    lowered = eng_name.lower()
    if lowered in _MYTH_EXCEPTIONS:
        return False
    return any(ch in lowered for ch in _WESTERN_LETTERS)


async def list_typecast_voices() -> list[dict]:
    """타입캐스트 목소리 전체를 {id, name, label, gender_key, age_key, use_case_keys, korean,
    search_text, preview_url} 형태로 돌려준다. 한국어권이 아닌 것 같은 목소리는 지우지 않고
    korean=False로 표시만 해둔다 (_looks_non_korean 참고) — 검색 쪽에서 걸러 보여준다.

    TYPECAST_API_KEY가 없으면 빈 목록을 돌려준다 (Polly처럼 유료 기능이라, 키가
    없는 서버에서는 그냥 안 보이는 게 맞다).
    """
    global _typecast_catalog_cache
    if _typecast_catalog_cache is not None:
        return _typecast_catalog_cache

    api_key = os.getenv("TYPECAST_API_KEY", "")
    if not api_key:
        return []

    async with aiohttp.ClientSession() as session:
        async with session.get(_TYPECAST_VOICES_URL, headers={"X-API-KEY": api_key}) as resp:
            resp.raise_for_status()
            raw = await resp.json()

    catalog = []
    for v in raw:
        names = v.get("voice_name", {})

        kor_name = names.get("kor") or names.get("eng") or v["voice_id"]
        eng_name = names.get("eng", "")
        gender = _GENDER_KO.get(v.get("gender"), "")
        age = _AGE_KO.get(v.get("age"), "")
        use_case_keys = list(v.get("use_cases", []))
        use_cases = ", ".join(USE_CASES_KO.get(u, u) for u in use_case_keys)
        descriptor = " · ".join(part for part in (gender, age) if part)
        label = f"{kor_name} ({descriptor})" if descriptor else kor_name

        catalog.append(
            {
                "id": f"typecast_id:{v['voice_id']}",
                "name": kor_name,
                "label": label,
                "gender": gender,
                "age": age,
                "use_cases": use_cases,
                "gender_key": v.get("gender") or "",
                "age_key": v.get("age") or "",
                "use_case_keys": use_case_keys,
                "korean": not _looks_non_korean(names),
                "preview_url": v.get("preview_url"),
                "search_text": f"{kor_name} {eng_name} {gender} {age} {use_cases} {' '.join(use_case_keys)}".lower(),
            }
        )

    _typecast_catalog_cache = catalog
    return catalog


async def search_typecast_voices(
    query: str = "",
    limit: int = 1000,
    gender: str = "",
    age: str = "",
    use_case: str = "",
    korean_only: bool = True,
) -> list[dict]:
    """이름/성별/나이/용도로 부분 일치 검색 + 조건 필터.

    gender("male"/"female"), age("child"/"teenager"/"young_adult"/"middle_age"/"elder"),
    use_case(USE_CASES_KO의 영어 값)는 비워두면 조건 없음이고, 여러 개를 주면 모두
    만족하는 것만 나온다. korean_only가 True면 한국어권이 아닌 것 같은 목소리는 뺀다.
    검색어도 비어있으면 조건에 맞는 전체 목록(앞에서부터 limit개)을 돌려준다 —
    뭘 검색해야 할지 모를 때 그냥 목록을 훑어볼 수 있게."""
    catalog = await list_typecast_voices()
    q = query.strip().lower()
    return [
        v
        for v in catalog
        if (not korean_only or v["korean"])
        and (not gender or v["gender_key"] == gender)
        and (not age or v["age_key"] == age)
        and (not use_case or use_case in v["use_case_keys"])
        and (not q or q in v["search_text"])
    ][:limit]


async def find_typecast_voice(voice_id: str) -> dict | None:
    """id("typecast_id:...")로 카탈로그에서 딱 하나 찾는다. 이미 골라놓은 목소리를
    다시 화면에 보여줄 때(검색을 다시 안 해도 되게) 쓴다."""
    for v in await list_typecast_voices():
        if v["id"] == voice_id:
            return v
    return None
