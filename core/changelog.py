# -*- coding: utf-8 -*-
"""
CHANGELOG.md를 읽어서 "날짜별 업데이트 항목 목록"으로 바꿔주는 코드.

예전엔 봇이 켜질 때마다 최신 항목을 업데이트 로그 채널에 자동으로 올렸지만, 이제는
올릴 내용을 관리자가 직접 고른다. 웹 설정 페이지의 "업데이트 로그"가 이 모듈로 항목들을
읽어와서 체크박스로 보여주고, 관리자가 고른 것만 채널에 게시한다. 코드를 고칠 때
CHANGELOG.md 맨 위에 "## 날짜" 항목과 "- 내용" 줄들을 추가해두면 그 페이지에 나타난다.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def item_key(date: str, text: str) -> str:
    """항목 하나를 구분하는 짧은 키. 어떤 항목을 이미 올렸는지 기억해두는 데 쓴다."""
    return hashlib.sha1(f"{date}\n{text}".encode("utf-8")).hexdigest()[:12]


def parse_entries() -> list[dict]:
    """CHANGELOG.md를 [{"date": "2026-10-09", "items": [{"key": ..., "text": ...}, ...]}, ...]
    (파일에 적힌 순서 그대로, 즉 최신 날짜가 먼저)로 돌려준다. 파일이 없으면 빈 목록.

    "## 날짜" 줄이 새 항목의 시작이고, 그 아래 "- "로 시작하는 줄 하나가 업데이트 내용 하나다.
    들여쓰기로 이어진 줄은 바로 앞 내용의 뒷부분으로 붙인다.
    """
    if not CHANGELOG_PATH.exists():
        return []

    entries: list[dict] = []
    current: dict | None = None
    texts: list[str] | None = None

    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = {"date": line[3:].strip(), "items": []}
            texts = []
            entries.append(current)
        elif current is not None and texts is not None:
            if line.startswith("- "):
                texts.append(line[2:].strip())
            elif line.startswith((" ", "\t")) and line.strip() and texts:
                texts[-1] += " " + line.strip()
            else:
                continue
            current["items"] = [{"key": item_key(current["date"], t), "text": t} for t in texts]

    return [e for e in entries if e["items"]]
