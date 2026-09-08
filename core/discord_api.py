# -*- coding: utf-8 -*-
"""
디스코드 REST API를 직접 호출하는 아주 얇은 래퍼.

웹 설정 페이지(web/app.py)는 실행 중인 봇(main.py)과 완전히 다른 프로세스라서, 봇이
디스코드와 맺고 있는 실시간 연결(게이트웨이)을 함께 쓸 수 없다. 대신 디스코드가 제공하는
REST API를 봇 토큰으로 직접 호출해서 "채널/역할/멤버 목록 가져오기", "메시지 보내기",
"채널 만들기" 같은 일회성 작업을 처리한다.

이렇게 REST로 직접 호출하면 main.py(봇)가 꺼져 있어도 설정 페이지 자체는 동작한다.
다만 이모지를 눌렀을 때 실제로 역할이 부여되거나, 음성채널이 자동 생성되는 것은
main.py가 켜져 있어야 일어난다 (그건 실시간 감시가 필요한 일이라서).
"""
from __future__ import annotations

import os
from urllib.parse import quote

import requests

API_BASE = "https://discord.com/api/v10"


def _headers() -> dict:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
    return {"Authorization": f"Bot {token}"}


def get_bot_guilds() -> list[dict]:
    """봇이 들어가 있는 서버 목록."""
    r = requests.get(f"{API_BASE}/users/@me/guilds", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def get_channels(guild_id: int) -> list[dict]:
    """서버의 모든 채널(텍스트/음성/카테고리) 목록."""
    r = requests.get(f"{API_BASE}/guilds/{guild_id}/channels", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def get_roles(guild_id: int) -> list[dict]:
    """서버의 모든 역할 목록."""
    r = requests.get(f"{API_BASE}/guilds/{guild_id}/roles", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def get_members(guild_id: int, limit: int = 1000) -> list[dict]:
    """서버 멤버 목록. (디스코드 개발자 포털에서 SERVER MEMBERS INTENT를 켜야 값이 나온다)"""
    r = requests.get(
        f"{API_BASE}/guilds/{guild_id}/members", headers=_headers(), params={"limit": limit}, timeout=10
    )
    r.raise_for_status()
    return r.json()


def create_voice_channel(guild_id: int, name: str, parent_id: int | None = None) -> dict:
    """음성채널을 새로 만든다. type=2가 음성채널을 뜻하는 디스코드 API 코드다."""
    payload: dict = {"name": name, "type": 2}
    if parent_id:
        payload["parent_id"] = parent_id
    r = requests.post(f"{API_BASE}/guilds/{guild_id}/channels", headers=_headers(), json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def send_message(channel_id: int, embed: dict) -> dict:
    """채널에 임베드 메시지를 보낸다. 성공하면 생성된 메시지 정보(id 포함)를 돌려준다."""
    r = requests.post(
        f"{API_BASE}/channels/{channel_id}/messages", headers=_headers(), json={"embeds": [embed]}, timeout=10
    )
    r.raise_for_status()
    return r.json()


def add_reaction(channel_id: int, message_id: int, emoji: str) -> None:
    """메시지에 봇이 직접 이모지를 눌러(반응을 남겨) 사람들이 누를 자리를 만들어둔다."""
    encoded = quote(emoji)
    r = requests.put(
        f"{API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()


def add_role(guild_id: int, user_id: int, role_id: int) -> None:
    r = requests.put(
        f"{API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}", headers=_headers(), timeout=10
    )
    r.raise_for_status()


def remove_role(guild_id: int, user_id: int, role_id: int) -> None:
    r = requests.delete(
        f"{API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}", headers=_headers(), timeout=10
    )
    r.raise_for_status()
