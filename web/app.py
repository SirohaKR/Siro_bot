# -*- coding: utf-8 -*-
"""
어시스턴트 레일라 설정용 웹페이지.

봇 프로세스(main.py)와는 별개로 켜서 브라우저로 접속해 쓰는 "관리자 설정 페이지"다.
채널/역할을 고르고 버튼을 누르면 여기서 디스코드 REST API(core/discord_api.py)를
직접 호출해서:
  - 입장안내 채널에 "캐릭터 인증하러 가기" 버튼이 달린 안내 메시지를 올리거나
  - 길드 규칙/공지사항을 원하는 채널에 올리거나
  - 새 음성채널(파티모집 허브)을 만들거나
  - 멤버에게 길드 직급 역할을 부여한다.

버튼을 눌렀을 때 비공개 인증 스레드를 만들고, 관리자가 승인/거절해서 실제로 역할을
부여하는 것은 여기(REST API)가 아니라 실시간 연결이 필요한 main.py(cogs/verification.py)가
담당한다.

관리하는 항목이 여러 개라, 한 페이지에 다 몰아넣는 대신 항목별로 페이지를 나눴다
(입장 안내/캐릭터 인증/공지사항/파티모집/길드 직급/멤버 관리). 페이지마다 입력값을
모아서 맨 아래 버튼 하나로 저장/게시하는 방식은 그대로 유지한다.

그렇게 정해진 설정(어떤 메시지/채널/역할을 쓰는지)은 core/settings_store.py를 통해
data/settings.json에 저장된다. 실행 중인 봇(main.py)이 그 값을 계속 읽어서 실제 동작
(버튼 클릭 -> 인증 스레드 생성 -> 관리자 승인 -> 역할 부여, 허브 채널 입장 -> 개인 채널 생성)을
수행한다.

인증은 로그인 페이지(비밀번호 입력) 방식이다. 주소 자체에는 비밀 값이 없고,
처음 접속하면 /login으로 보내져서 WEB_ADMIN_TOKEN 값을 비밀번호로 입력해야 들어갈 수
있다. 한 번 입력하면 브라우저 세션 쿠키로 로그인 상태가 유지된다.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, send_from_directory, session, url_for

# "python web/app.py"로 실행하면 파이썬이 기본적으로 web/ 폴더만 찾다보니, 한 단계
# 위에 있는 core/ 폴더(core/discord_api.py, core/settings_store.py)를 못 찾아서
# "ModuleNotFoundError: No module named 'core'" 오류가 난다. 아래 줄로 프로젝트
# 최상위 폴더(main.py가 있는 곳)를 검색 경로에 직접 추가해서 해결한다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

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

# 캐릭터 그림 등 미리 준비해둔 이미지를 넣어두는 폴더. 공지/안내 이미지를 고를 때
# 매번 파일을 다시 올리지 않고 여기서 골라 쓸 수 있게 한다 (아래 "내장 이미지" 탭).
IMG_DIR = os.path.join(PROJECT_ROOT, "img")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _list_builtin_images() -> list[str]:
    if not os.path.isdir(IMG_DIR):
        return []
    found = []
    for root, _dirs, files in os.walk(IMG_DIR):
        for name in files:
            if name.lower().endswith(IMAGE_EXTENSIONS):
                rel = os.path.relpath(os.path.join(root, name), IMG_DIR)
                found.append(rel.replace(os.sep, "/"))
    return sorted(found)

ENTRANCE_BUTTON_COMPONENTS = [
    {
        "type": 1,
        "components": [
            {
                "type": 2,
                "style": 1,
                "label": "🔑 캐릭터 인증하러 가기",
                "custom_id": "siro:verify_start",
            }
        ],
    }
]


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


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    """img/ 폴더의 내장 이미지를 브라우저에 보여준다. (로그인 세션이 있어야 접근 가능)"""
    return send_from_directory(IMG_DIR, filename)


def _channels(guild_id: int) -> dict:
    channels = discord_api.get_channels(guild_id)
    return {
        "text_channels": [c for c in channels if c["type"] == 0],
        "voice_channels": [c for c in channels if c["type"] == 2],
        "categories": [c for c in channels if c["type"] == 4],
        "channels_by_id": {int(c["id"]): c["name"] for c in channels},
    }


def _roles(guild_id: int) -> tuple[list, dict]:
    roles = [r for r in discord_api.get_roles(guild_id) if r["name"] != "@everyone"]
    roles_by_id = {int(r["id"]): r["name"] for r in roles}
    return roles, roles_by_id


def _post_embed(channel_id: int, title: str, body: str, image_url: str, image_file, components=None) -> dict:
    """공지성 임베드 하나를 채널에 올린다. 파일 첨부가 있으면 그걸 우선한다."""
    embed = {"title": title, "description": body, "color": 0x5B8CFF}
    if image_file and image_file.filename:
        filename = image_file.filename
        embed["image"] = {"url": f"attachment://{filename}"}
        return discord_api.send_message_with_file(channel_id, embed, filename, image_file.read(), components)
    if image_url:
        embed["image"] = {"url": image_url}
    return discord_api.send_message(channel_id, embed, components)


@app.route("/guild/<int:guild_id>")
def guild_page(guild_id):
    settings = settings_store.get_guild_settings(guild_id)
    ch = _channels(guild_id)
    _, roles_by_id = _roles(guild_id)

    return render_template(
        "dashboard.html",
        guild_id=guild_id,
        active="dashboard",
        page_title="🏠 대시보드",
        page_desc="레일라가 지금 어떻게 설정되어 있는지 한눈에 볼 수 있어요.",
        settings=settings,
        entrance=settings.get("entrance", {}),
        verification=settings.get("verification", {}),
        announcement=settings.get("announcement", {}),
        rules=settings.get("guild_rules", {}),
        job_list=settings.get("job_list", []),
        rank_role_ids=settings.get("rank_role_ids", {}),
        guild_ranks=GUILD_RANKS,
        channels_by_id=ch["channels_by_id"],
        text_channels=ch["text_channels"],
        roles_by_id=roles_by_id,
    )


@app.route("/guild/<int:guild_id>/bot-log", methods=["POST"])
def set_bot_log_channel(guild_id):
    """업데이트 내역을 자동으로 남길 채널을 지정한다. main.py가 시작할 때(또는 새 버전이
    감지될 때) CHANGELOG.md의 최신 항목을 이 채널에 올려준다."""
    channel_id = request.form.get("channel_id")
    settings_store.update_guild_settings(guild_id, bot_log_channel_id=int(channel_id) if channel_id else None)
    return redirect(url_for("guild_page", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/entrance", methods=["GET", "POST"])
def guild_entrance(guild_id):
    """입장안내 채널에 "캐릭터 인증하러 가기" 버튼이 달린 안내 메시지를 올린다.

    이 버튼 자체는 REST API로 바로 만들 수 있지만, 눌렸을 때 비공개 인증 스레드를
    만드는 실제 동작은 실시간으로 켜져 있는 main.py(cogs/verification.py)가 처리한다.
    """
    if request.method == "POST":
        channel_id = int(request.form["channel_id"])
        title = (request.form.get("title") or "").strip() or "입장 안내"
        body = (request.form.get("body") or "").strip()
        image_url = (request.form.get("image_url") or "").strip()
        image_file = request.files.get("image_file")

        message = _post_embed(channel_id, title, body, image_url, image_file, ENTRANCE_BUTTON_COMPONENTS)

        settings_store.update_guild_settings(
            guild_id,
            entrance={"channel_id": channel_id, "title": title, "body": body, "message_id": int(message["id"])},
        )
        return redirect(url_for("guild_entrance", guild_id=guild_id))

    entrance = settings_store.get_guild_settings(guild_id).get("entrance", {})
    return render_template(
        "entrance.html",
        guild_id=guild_id,
        active="entrance",
        page_title="🚪 입장 안내",
        page_desc="새로 들어온 길드원에게 보여줄 안내 메시지를 만들어요.",
        text_channels=_channels(guild_id)["text_channels"],
        entrance=entrance,
        builtin_images=_list_builtin_images(),
    )


@app.route("/guild/<int:guild_id>/verification", methods=["GET", "POST"])
def guild_verification(guild_id):
    """캐릭터 인증 안내 문구 + 인증 스레드를 만들 채널 + 승인 시 부여할 역할을 저장한다.

    여기서 저장한 값은 바로 채널에 게시되는 게 아니라, 멤버가 입장안내의 버튼을 눌러
    비공개 인증 스레드가 만들어질 때마다 그 스레드 안에 안내 문구로 쓰인다.
    """
    if request.method == "POST":
        channel_id = int(request.form["channel_id"])
        role_id = int(request.form["role_id"])
        title = (request.form.get("title") or "").strip() or "캐릭터 인증"
        body = (request.form.get("body") or "").strip()
        log_channel_id = request.form.get("log_channel_id")

        settings = settings_store.get_guild_settings(guild_id)
        existing_threads = (settings.get("verification") or {}).get("threads", {})

        settings_store.update_guild_settings(
            guild_id,
            verification={
                "channel_id": channel_id,
                "role_id": role_id,
                "title": title,
                "body": body,
                "threads": existing_threads,
                "log_channel_id": int(log_channel_id) if log_channel_id else None,
            },
        )
        return redirect(url_for("guild_verification", guild_id=guild_id))

    ch = _channels(guild_id)
    roles, _ = _roles(guild_id)
    verification = settings_store.get_guild_settings(guild_id).get("verification", {})
    return render_template(
        "verification.html",
        guild_id=guild_id,
        active="verification",
        page_title="🔑 캐릭터 인증",
        page_desc="입장 안내 버튼을 누르면 만들어지는 비공개 채널의 안내와, 승인 시 부여할 역할을 설정해요.",
        text_channels=ch["text_channels"],
        roles=roles,
        verification=verification,
    )


@app.route("/guild/<int:guild_id>/announcements", methods=["GET", "POST"])
def guild_announcements(guild_id):
    """이벤트/소식처럼 그때그때 알릴 공지사항을 원하는 채널에 올린다. 누를 때마다 새
    메시지로 게시된다 (계속 남겨둘 내용은 "길드 규칙" 페이지를 쓴다)."""
    if request.method == "POST":
        channel_id = int(request.form["channel_id"])
        title = (request.form.get("title") or "").strip() or "공지"
        body = (request.form.get("body") or "").strip()
        image_url = (request.form.get("image_url") or "").strip()
        image_file = request.files.get("image_file")

        message = _post_embed(channel_id, title, body, image_url, image_file)

        settings_store.update_guild_settings(
            guild_id,
            announcement={"channel_id": channel_id, "title": title, "body": body, "message_id": int(message["id"])},
        )
        return redirect(url_for("guild_announcements", guild_id=guild_id))

    announcement = settings_store.get_guild_settings(guild_id).get("announcement", {})
    return render_template(
        "announcements.html",
        guild_id=guild_id,
        active="announcements",
        page_title="📢 공지사항",
        page_desc="이벤트, 소식 등 그때그때 알릴 내용을 채널에 올려요. 누를 때마다 새 메시지로 게시돼요.",
        text_channels=_channels(guild_id)["text_channels"],
        announcement=announcement,
        builtin_images=_list_builtin_images(),
    )


@app.route("/guild/<int:guild_id>/rules", methods=["GET", "POST"])
def guild_rules(guild_id):
    """길드 규칙처럼 계속 남겨둘 안내를 채널에 올린다. 공지사항과 저장 위치만 다를 뿐
    동작은 동일하다 (구조를 나눈 이유는 07-14 업데이트로 두 기능을 분리했기 때문)."""
    if request.method == "POST":
        channel_id = int(request.form["channel_id"])
        title = (request.form.get("title") or "").strip() or "길드 규칙"
        body = (request.form.get("body") or "").strip()
        image_url = (request.form.get("image_url") or "").strip()
        image_file = request.files.get("image_file")

        message = _post_embed(channel_id, title, body, image_url, image_file)

        settings_store.update_guild_settings(
            guild_id,
            guild_rules={"channel_id": channel_id, "title": title, "body": body, "message_id": int(message["id"])},
        )
        return redirect(url_for("guild_rules", guild_id=guild_id))

    rules = settings_store.get_guild_settings(guild_id).get("guild_rules", {})
    return render_template(
        "rules.html",
        guild_id=guild_id,
        active="rules",
        page_title="📜 길드 규칙",
        page_desc="계속 남겨둘 길드 규칙을 채널에 올려요. 다시 게시하면 새 메시지로 올라가니, 이전 메시지는 직접 지워주세요.",
        text_channels=_channels(guild_id)["text_channels"],
        rules=rules,
        builtin_images=_list_builtin_images(),
    )


def _save_job_draft(guild_id: int) -> None:
    """공지 제목/본문 입력값을 저장해둔다. (이미지는 파일 첨부라 새로고침 후 되살릴 수
    없으므로 드래프트로 관리하지 않고, 게시할 때만 그 자리에서 첨부받는다)

    "목록에 추가"/"삭제"를 누를 때마다 페이지가 새로고침되는데, 그때 지금까지
    입력해둔 공지 내용이 날아가지 않도록 매번 같이 저장해서 다시 채워 넣는다.
    """
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    settings_store.update_guild_settings(guild_id, job_announcement_draft={"title": title, "body": body})


@app.route("/guild/<int:guild_id>/jobs")
def guild_jobs(guild_id):
    """채팅채널에 공지를 올리고 이모지 반응으로 역할을 셀프 선택하게 하는 페이지.

    캐릭터 인증(관리자 승인이 필요한 방식)과는 별개로, 직업처럼 "여러 개 중 하나를
    본인이 바로 고르면 되는" 역할에 쓰는 셀프 선택형 기능이다. 실제 반응 감지/역할
    부여는 cogs/roles.py가 담당한다.
    """
    settings = settings_store.get_guild_settings(guild_id)
    roles, roles_by_id = _roles(guild_id)
    return render_template(
        "jobs.html",
        guild_id=guild_id,
        active="jobs",
        page_title="🎭 직업 선택 (이모지 역할)",
        page_desc="채팅 채널에 공지를 올리고, 길드원이 이모티콘을 눌러 직업 역할을 스스로 고르게 해요.",
        text_channels=_channels(guild_id)["text_channels"],
        roles=roles,
        roles_by_id=roles_by_id,
        job_list=settings.get("job_list", []),
        announcement_draft=settings.get("job_announcement_draft", {}),
        settings=settings,
        builtin_images=_list_builtin_images(),
    )


@app.route("/guild/<int:guild_id>/jobs/add", methods=["POST"])
def add_job(guild_id):
    """직업 목록에 한 줄 추가한다 (직업 이름 + 이모지 + 역할). 개수 제한 없음."""
    _save_job_draft(guild_id)

    label = (request.form.get("label") or "").strip()
    emoji = (request.form.get("emoji") or "").strip()
    role_id = request.form.get("role_id")

    if label and emoji and role_id:
        settings = settings_store.get_guild_settings(guild_id)
        job_list = settings.get("job_list", [])
        job_list.append({"label": label, "emoji": emoji, "role_id": int(role_id)})
        settings_store.update_guild_settings(guild_id, job_list=job_list)

    return redirect(url_for("guild_jobs", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/jobs/delete", methods=["POST"])
def delete_job(guild_id):
    """직업 목록에서 한 줄을 뺀다."""
    _save_job_draft(guild_id)

    index = request.form.get("index", type=int)
    settings = settings_store.get_guild_settings(guild_id)
    job_list = settings.get("job_list", [])

    if index is not None and 0 <= index < len(job_list):
        job_list.pop(index)
        settings_store.update_guild_settings(guild_id, job_list=job_list)

    return redirect(url_for("guild_jobs", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/jobs/post", methods=["POST"])
def post_job_roles(guild_id):
    """직접 쓴 공지 제목/본문/이미지 + 지금까지 추가해둔 직업 목록으로 실제 공지
    메시지를 올리고, 그 밑에 이모지를 붙인다."""
    channel_id = int(request.form["channel_id"])
    title = (request.form.get("title") or "").strip() or "공지"
    body = (request.form.get("body") or "").strip()
    image_url = (request.form.get("image_url") or "").strip()
    image_file = request.files.get("image_file")
    _save_job_draft(guild_id)

    settings = settings_store.get_guild_settings(guild_id)
    job_list = settings.get("job_list", [])

    if not job_list:
        return redirect(url_for("guild_jobs", guild_id=guild_id))

    emoji_to_role = {}
    lines = []
    for job in job_list:
        emoji_to_role[job["emoji"]] = {"role_id": job["role_id"], "label": job["label"]}
        lines.append(f"{job['emoji']}  {job['label']}")

    # 관리자가 직접 쓴 공지 내용 밑에, 어떤 이모지가 어떤 역할인지 목록을 이어 붙인다.
    description = body
    if lines:
        description += ("\n\n" if description else "") + "\n".join(lines)

    message = _post_embed(channel_id, title, description, image_url, image_file)

    for emoji in emoji_to_role:
        discord_api.add_reaction(channel_id, message["id"], emoji)

    settings_store.update_guild_settings(
        guild_id,
        job_roles={
            "message_id": int(message["id"]),
            "channel_id": channel_id,
            "emoji_to_role": emoji_to_role,
        },
    )
    return redirect(url_for("guild_jobs", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/hub")
def guild_hub(guild_id):
    ch = _channels(guild_id)
    settings = settings_store.get_guild_settings(guild_id)
    return render_template(
        "hub.html",
        guild_id=guild_id,
        active="hub",
        page_title="🔊 음성 채널 자동 생성",
        page_desc="채널에 들어가면 개인/자유 음성방이 자동으로 생기게 해요. 허브는 원하는 만큼 추가할 수 있어요.",
        voice_channels=ch["voice_channels"],
        categories=ch["categories"],
        channels_by_id=ch["channels_by_id"],
        voice_hubs=settings.get("voice_hubs", []),
    )


@app.route("/guild/<int:guild_id>/hub/add", methods=["POST"])
def add_voice_hub(guild_id):
    """음성 허브를 하나 추가한다. 기존 채널을 고르거나, 이름을 입력해 새로 만들 수 있다.

    name_template 안의 {user}는 입장한 사람 이름, {n}은 그 허브에서 몇 번째로 만든
    채널인지로 바뀐다 (실제 치환은 cogs/channels.py가 한다). 화면에는 자주 쓰는 형태
    (이름별/번호별/자유) 버튼을 미리 만들어뒀지만, 직접 원하는 문구로 바꿔도 된다.
    """
    existing_id = request.form.get("existing_channel_id")
    new_name = (request.form.get("new_channel_name") or "").strip()
    parent_id = request.form.get("parent_id") or None
    name_template = (request.form.get("name_template") or "").strip() or "{user}의 방"

    if existing_id:
        hub_channel_id = int(existing_id)
    elif new_name:
        channel = discord_api.create_voice_channel(guild_id, new_name, int(parent_id) if parent_id else None)
        hub_channel_id = int(channel["id"])
    else:
        return redirect(url_for("guild_hub", guild_id=guild_id))

    settings = settings_store.get_guild_settings(guild_id)
    voice_hubs = settings.get("voice_hubs", [])
    voice_hubs.append({"id": hub_channel_id, "name_template": name_template, "counter": 0})
    settings_store.update_guild_settings(guild_id, voice_hubs=voice_hubs)
    return redirect(url_for("guild_hub", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/hub/delete", methods=["POST"])
def delete_voice_hub(guild_id):
    """음성 허브 설정을 하나 뺀다. (허브로 쓰던 디스코드 채널 자체는 지우지 않는다)"""
    index = request.form.get("index", type=int)
    settings = settings_store.get_guild_settings(guild_id)
    voice_hubs = settings.get("voice_hubs", [])

    if index is not None and 0 <= index < len(voice_hubs):
        voice_hubs.pop(index)
        settings_store.update_guild_settings(guild_id, voice_hubs=voice_hubs)

    return redirect(url_for("guild_hub", guild_id=guild_id))


@app.route("/guild/<int:guild_id>/ranks", methods=["GET", "POST"])
def guild_ranks(guild_id):
    if request.method == "POST":
        rank_role_ids = {}
        for rank in GUILD_RANKS:
            role_id = request.form.get(f"role_{rank}")
            if role_id:
                rank_role_ids[rank] = int(role_id)
        settings_store.update_guild_settings(guild_id, rank_role_ids=rank_role_ids)
        return redirect(url_for("guild_ranks", guild_id=guild_id))

    roles, _ = _roles(guild_id)
    rank_role_ids = settings_store.get_guild_settings(guild_id).get("rank_role_ids", {})
    return render_template(
        "ranks.html",
        guild_id=guild_id,
        active="ranks",
        page_title="👑 길드 직급",
        page_desc="길드마스터/부길드장 같은 직급에 서버 역할을 연결해요.",
        roles=roles,
        guild_ranks=GUILD_RANKS,
        rank_role_ids=rank_role_ids,
    )


@app.route("/guild/<int:guild_id>/members", methods=["GET", "POST"])
def guild_members(guild_id):
    if request.method == "POST":
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

        return redirect(url_for("guild_members", guild_id=guild_id))

    settings = settings_store.get_guild_settings(guild_id)
    rank_role_ids: dict = settings.get("rank_role_ids", {})
    role_id_to_rank = {str(role_id): rank for rank, role_id in rank_role_ids.items()}

    members_raw = discord_api.get_members(guild_id)
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

    return render_template(
        "members.html",
        guild_id=guild_id,
        active="members",
        page_title="🧑‍🤝‍🧑 역할 부여",
        page_desc="멤버를 골라서 직급 역할을 직접 부여해요 (셀프 지급 아님).",
        members=sorted(members, key=lambda m: m["name"].lower()),
        guild_ranks=GUILD_RANKS,
    )


if __name__ == "__main__":
    port = int(os.getenv("WEB_PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
