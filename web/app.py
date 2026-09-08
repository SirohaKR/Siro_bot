# -*- coding: utf-8 -*-
"""
시로냥 설정용 웹페이지.

봇 프로세스(main.py)와는 별개로 켜서 브라우저로 접속해 쓰는 "관리자 설정 페이지"다.
채널/역할을 고르고 버튼을 누르면 여기서 디스코드 REST API(core/discord_api.py)를
직접 호출해서:
  - 공지 채널에 "직업 선택" 메시지를 올리고 이모티콘을 붙이거나
  - 새 음성채널(파티모집 허브)을 만들거나
  - 멤버에게 길드 직급 역할을 부여한다.

그렇게 정해진 설정(어떤 메시지/채널/역할을 쓰는지)은 core/settings_store.py를 통해
data/settings.json에 저장된다. 실행 중인 봇(main.py)이 그 값을 계속 읽어서 실제 동작
(이모지 반응 감지 -> 역할 부여, 허브 채널 입장 -> 개인 채널 생성)을 수행한다.

인증은 로그인 페이지(비밀번호 입력) 방식이다. 주소 자체에는 비밀 값이 없고,
처음 접속하면 /login으로 보내져서 WEB_ADMIN_TOKEN 값을 비밀번호로 입력해야 들어갈 수
있다. 한 번 입력하면 브라우저 세션 쿠키로 로그인 상태가 유지된다.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

# "python web/app.py"로 실행하면 파이썬이 기본적으로 web/ 폴더만 찾다보니, 한 단계
# 위에 있는 core/ 폴더(core/discord_api.py, core/settings_store.py)를 못 찾아서
# "ModuleNotFoundError: No module named 'core'" 오류가 난다. 아래 줄로 프로젝트
# 최상위 폴더(main.py가 있는 곳)를 검색 경로에 직접 추가해서 해결한다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import discord_api, settings_store  # noqa: E402

load_dotenv()

WEB_ADMIN_TOKEN = os.getenv("WEB_ADMIN_TOKEN")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

if not WEB_ADMIN_TOKEN:
    print("⚠️ [WARN] WEB_ADMIN_TOKEN이 설정되지 않았습니다. 아무도 로그인할 수 없습니다 (.env 확인).")

# 길드 직급 목록 (위쪽일수록 높은 직급). 이모지로 셀프 지급하면 아무나 "길드마스터"를
# 누를 수 있게 되므로, 직급은 아래 멤버 목록에서 관리자가 직접 눌러서만 부여한다.
GUILD_RANKS = ["길드마스터", "부길드장", "길드원", "신입길드원"]


@app.before_request
def require_auth():
    if request.endpoint in ("static", "login"):
        return None
    if session.get("authed"):
        return None
    return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if WEB_ADMIN_TOKEN and request.form.get("password") == WEB_ADMIN_TOKEN:
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("index"))
        return render_template("login.html", error=True)
    return render_template("login.html", error=False)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    guilds = discord_api.get_bot_guilds()
    if len(guilds) == 1:
        return redirect(url_for("guild_page", guild_id=guilds[0]["id"]))
    return render_template("index.html", guilds=guilds)


def _load_guild_context(guild_id: int) -> dict:
    channels = discord_api.get_channels(guild_id)
    roles = [r for r in discord_api.get_roles(guild_id) if r["name"] != "@everyone"]
    members_raw = discord_api.get_members(guild_id)

    settings = settings_store.get_guild_settings(guild_id)
    rank_role_ids: dict = settings.get("rank_role_ids", {})
    role_id_to_rank = {str(role_id): rank for rank, role_id in rank_role_ids.items()}
    roles_by_id = {int(r["id"]): r["name"] for r in roles}

    members = []
    for m in members_raw:
        if m["user"].get("bot"):
            continue
        member_role_ids = m.get("roles", [])
        current_rank = next((role_id_to_rank[rid] for rid in member_role_ids if rid in role_id_to_rank), None)
        members.append(
            {
                "id": m["user"]["id"],
                "name": m.get("nick") or m["user"]["username"],
                "current_rank": current_rank,
            }
        )

    return {
        "guild_id": guild_id,
        "text_channels": [c for c in channels if c["type"] == 0],
        "voice_channels": [c for c in channels if c["type"] == 2],
        "categories": [c for c in channels if c["type"] == 4],
        "roles": roles,
        "roles_by_id": roles_by_id,
        "members": sorted(members, key=lambda m: m["name"].lower()),
        "settings": settings,
        "job_list": settings.get("job_list", []),
        "guild_ranks": GUILD_RANKS,
        "rank_role_ids": rank_role_ids,
    }


@app.route("/guild/<int:guild_id>")
def guild_page(guild_id):
    return render_template("settings.html", **_load_guild_context(guild_id))


@app.route("/guild/<int:guild_id>/jobs/add", methods=["POST"])
def add_job(guild_id):
    """직업 목록에 한 줄 추가한다 (직업 이름 + 이모지 + 역할). 개수 제한 없음."""
    label = (request.form.get("label") or "").strip()
    emoji = (request.form.get("emoji") or "").strip()
    role_id = request.form.get("role_id")

    if label and emoji and role_id:
        settings = settings_store.get_guild_settings(guild_id)
        job_list = settings.get("job_list", [])
        job_list.append({"label": label, "emoji": emoji, "role_id": int(role_id)})
        settings_store.update_guild_settings(guild_id, job_list=job_list)

    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/jobs/delete", methods=["POST"])
def delete_job(guild_id):
    """직업 목록에서 한 줄을 뺀다."""
    index = request.form.get("index", type=int)
    settings = settings_store.get_guild_settings(guild_id)
    job_list = settings.get("job_list", [])

    if index is not None and 0 <= index < len(job_list):
        job_list.pop(index)
        settings_store.update_guild_settings(guild_id, job_list=job_list)

    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/job-roles", methods=["POST"])
def post_job_roles(guild_id):
    """지금까지 추가해둔 직업 목록으로 실제 공지 메시지를 올리고 이모지를 붙인다."""
    channel_id = int(request.form["channel_id"])
    settings = settings_store.get_guild_settings(guild_id)
    job_list = settings.get("job_list", [])

    if not job_list:
        return redirect(url_for("guild_page", guild_id=guild_id))

    emoji_to_role = {}
    lines = []
    for job in job_list:
        emoji_to_role[job["emoji"]] = {"role_id": job["role_id"], "label": job["label"]}
        lines.append(f"{job['emoji']}  {job['label']}")

    embed = {
        "title": "🍁 직업을 선택해주세요",
        "description": "아래 이모티콘을 누르면 해당 직업 역할이 자동으로 부여됩니다.\n\n" + "\n".join(lines),
        "color": 0x57F287,
    }
    message = discord_api.send_message(channel_id, embed)
    for emoji in emoji_to_role:
        discord_api.add_reaction(channel_id, message["id"], emoji)

    settings_store.update_guild_settings(
        guild_id,
        announcement_channel_id=channel_id,
        job_roles={
            "message_id": int(message["id"]),
            "channel_id": channel_id,
            "emoji_to_role": emoji_to_role,
        },
    )
    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/rank-roles", methods=["POST"])
def post_rank_roles(guild_id):
    rank_role_ids = {}
    for rank in GUILD_RANKS:
        role_id = request.form.get(f"role_{rank}")
        if role_id:
            rank_role_ids[rank] = int(role_id)
    settings_store.update_guild_settings(guild_id, rank_role_ids=rank_role_ids)
    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/assign-rank", methods=["POST"])
def assign_rank(guild_id):
    member_id = int(request.form["member_id"])
    rank = request.form["rank"]

    settings = settings_store.get_guild_settings(guild_id)
    rank_role_ids: dict = settings.get("rank_role_ids", {})
    target_role_id = rank_role_ids.get(rank)

    if target_role_id:
        # 직급은 한 사람당 하나만 갖도록, 다른 직급 역할은 제거하고 새 직급만 부여한다.
        for other_rank, role_id in rank_role_ids.items():
            if role_id != target_role_id:
                try:
                    discord_api.remove_role(guild_id, member_id, role_id)
                except Exception:
                    pass  # 원래 그 직급이 아니었을 수도 있으니 실패해도 무시.
        discord_api.add_role(guild_id, member_id, target_role_id)

    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/hub-channel", methods=["POST"])
def post_hub_channel(guild_id):
    existing_id = request.form.get("existing_channel_id")
    new_name = (request.form.get("new_channel_name") or "").strip()
    parent_id = request.form.get("parent_id") or None

    if existing_id:
        hub_channel_id = int(existing_id)
    elif new_name:
        channel = discord_api.create_voice_channel(guild_id, new_name, int(parent_id) if parent_id else None)
        hub_channel_id = int(channel["id"])
    else:
        return redirect(url_for("guild_page", guild_id=guild_id))

    settings_store.update_guild_settings(guild_id, hub_voice_channel_id=hub_channel_id)
    return redirect(url_for("guild_page", guild_id=guild_id))


if __name__ == "__main__":
    port = int(os.getenv("WEB_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
