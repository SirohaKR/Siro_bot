# -*- coding: utf-8 -*-
"""
서버(길드)별 설정을 저장하고 불러오는 아주 단순한 저장소.

데이터베이스(DB) 대신 JSON 파일 하나(data/settings.json)를 쓰는 이유:
- 서버 하나당 저장할 값이 몇 개 안 되고 자주 바뀌지도 않는다.
- 메모장으로 열어봐도 내용을 바로 알아볼 수 있어서, 파이썬을 몰라도
  data/settings.json을 직접 열어 값을 확인하거나 고칠 수 있다.

저장되는 값 예시 (서버 ID마다 하나씩):
{
  "123456789012345678": {
    "entrance": {"channel_id": 111, "title": "...", "body": "...", "message_id": 999},
    "verification": {
      "channel_id": 222,
      "title": "...",
      "body": "...",
      "role_id": 333,
      "threads": {"444(유저ID)": 555(스레드ID)}
    },
    "rank_role_ids": {"길드마스터": 333, ...},
    "hub_voice_channel_id": 444,
    "temp_voice_channel_ids": [555, 666]
  }
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"


def _load_all() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_all(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_guild_settings(guild_id: int) -> dict:
    """특정 서버의 설정을 딕셔너리로 가져온다. 아직 설정한 적이 없으면 빈 딕셔너리를 준다."""
    all_data = _load_all()
    return all_data.get(str(guild_id), {})


def update_guild_settings(guild_id: int, **kwargs: Any) -> None:
    """특정 서버의 설정 중 넘겨받은 값들만 덮어써서 저장한다.

    예) update_guild_settings(guild.id, hub_voice_channel_id=123)
    """
    all_data = _load_all()
    guild_key = str(guild_id)
    guild_data = all_data.get(guild_key, {})
    guild_data.update(kwargs)
    all_data[guild_key] = guild_data
    _save_all(all_data)
