# -*- coding: utf-8 -*-
"""
웹 설정 페이지에서 채널에 올린 글(공지사항, 길드 규칙, 입장 안내, 역할 선택, 업데이트
로그)을 날짜와 함께 data/post_log.txt에 계속 이어서 적어두는 기록 파일.

디스코드에서 메시지를 지우거나 고쳐도 "언제, 어느 채널에, 무슨 내용을 올렸는지"를 나중에
메모장으로 열어 볼 수 있게 하려는 용도다. data/ 폴더는 도커에서도 호스트와 공유되는
폴더라 컨테이너를 다시 만들어도 남는다. 시간은 한국 시간(KST) 기준으로 적는다.

기록하다 실패해도(디스크 문제 등) 글 올리기 자체가 막히면 안 되므로, 호출하는 쪽이
예외를 삼키도록 log_post()는 예외를 밖으로 던지지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import settings_store

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어서 고정 오프셋으로 충분하다.
LOG_FILENAME = "post_log.txt"


def log_post(
    guild_id: int,
    kind: str,
    channel_id: int,
    channel_name: str | None,
    title: str,
    body: str,
    message_id: int | str | None = None,
    image: str | None = None,
) -> None:
    """글 하나를 기록 파일 맨 아래에 덧붙인다 (기존 내용은 건드리지 않는다)."""
    try:
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        channel_label = f"#{channel_name}" if channel_name else "(채널 이름 모름)"
        header = f"[{now} KST] {kind} → {channel_label}"
        meta = f"서버 ID {guild_id} · 채널 ID {channel_id}"
        if message_id:
            meta += f" · 메시지 ID {message_id}"

        lines = [
            "=" * 64,
            header,
            meta,
            f"제목: {title}",
            f"이미지: {image or '없음'}",
            "-" * 64,
            body.rstrip() if body else "(내용 없음)",
            "",
            "",
        ]

        settings_store.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(settings_store.DATA_DIR / LOG_FILENAME, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:  # noqa: BLE001 - 기록 실패가 게시를 막으면 안 된다.
        print(f"⚠️ 게시 기록 파일 쓰기 실패: {e}")
