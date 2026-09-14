# -*- coding: utf-8 -*-
# 시로냥 봇 부트스트랩 — 메이플스토리 길드 관리용 (역할 지정 / 채널 관리 담당)
#
# 이 파일 하나로 봇을 켜고 끈다. 실제 기능은 cogs/verification.py, cogs/channels.py에 나눠져 있고,
# 이 파일은 그 기능들을 불러와서(load_extension) 디스코드에 접속시키는 역할만 한다.
#
# 참고: 역할/채널을 "무엇으로 설정할지"는 이 봇이 아니라 web/app.py(브라우저로 여는 설정
# 페이지)에서 관리한다. main.py는 그 설정을 읽어서 실제로 인증 버튼 클릭/이미지 업로드를
# 감시하고 음성채널을 자동 생성/삭제하는, 항상 켜져 있어야 하는 "실행" 담당이다.

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from core.changelog import get_latest_entry
from core.settings_store import get_guild_settings, update_guild_settings

load_dotenv()  # .env 파일에 적어둔 DISCORD_TOKEN 같은 값을 읽어온다.

TOKEN = os.getenv("DISCORD_TOKEN")

# 새 기능(cog)을 추가할 때는 여기에 모듈 경로만 한 줄 추가하면 된다.
INITIAL_EXTENSIONS = [
    "cogs.verification",  # 입장안내 버튼 -> 캐릭터 인증 스레드 -> 관리자 승인/거절
    "cogs.roles",  # 채팅채널에 올린 공지 + 이모지 반응으로 직업 등 역할 셀프 선택
    "cogs.channels",
    "cogs.tts",  # 지정한 텍스트채널의 글을 음성채널에서 읽어주는 TTS
    "cogs.info",  # "/설정" 명령어 — 웹 설정 페이지 주소를 알려줌
]

# Intents(인텐트) = 봇이 디스코드로부터 받을 이벤트의 종류를 미리 선언하는 것.
# members: 서버 멤버 정보를 읽고 역할을 부여/제거하기 위해 필요 (디스코드 개발자 포털에서
#          "SERVER MEMBERS INTENT"도 함께 켜야 한다. README.md 참고)
# voice_states: 누가 음성채널에 들어오고 나가는지 감지(파티모집 채널 기능)하기 위해 필요.
# message_content: 캐릭터 인증 스레드에 올라온 이미지 첨부파일을 읽으려면 필요하다.
#          (디스코드 개발자 포털에서 "MESSAGE CONTENT INTENT"도 함께 켜야 한다. README.md 참고)
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("\n" + "=" * 40)
    print(f"봇 이름: {bot.user.name}")
    print(f"봇 ID: {bot.user.id}")
    print("✅ 시로냥 봇 실행/연결 완료")

    try:
        synced = await bot.tree.sync()
        print(f"🌳 슬래시 명령어 글로벌 동기화 완료 ({len(synced)}개)")
    except Exception as e:
        print(f"⚠️ 슬래시 명령어 글로벌 동기화 실패: {e}")

    # 글로벌 동기화는 각 서버에 실제로 반영되기까지 최대 1시간까지 걸릴 수 있다.
    # .env에 MY_GUILD_ID(길드마스터가 쓰는 서버 ID)를 적어두면, 그 서버에는
    # 디스코드 쪽 지연 없이 바로 명령어가 뜨게 별도로 동기화해준다.
    guild_id = os.getenv("MY_GUILD_ID")
    if guild_id:
        try:
            guild_obj = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild_obj)
            synced_guild = await bot.tree.sync(guild=guild_obj)
            print(f"🌳 슬래시 명령어 길드 동기화 완료 (guild={guild_id}, {len(synced_guild)}개)")
        except Exception as e:
            print(f"⚠️ 슬래시 명령어 길드 동기화 실패: {e}")

    print("=" * 40 + "\n")

    await _announce_update()


async def _announce_update():
    """CHANGELOG.md의 최신 항목을, 아직 못 본 서버들의 '업데이트 로그' 채널에 알려준다.

    서버별로 core/settings_store.py의 last_announced_version과 비교해서, 이미 알려준
    버전이면 건너뛴다 — 재접속으로 on_ready가 여러 번 불려도 중복으로 올라가지 않는다.
    """
    entry = get_latest_entry()
    if entry is None:
        return
    version, body = entry

    for guild in bot.guilds:
        settings = get_guild_settings(guild.id)
        log_channel_id = settings.get("bot_log_channel_id")
        if not log_channel_id or settings.get("last_announced_version") == version:
            continue

        channel = guild.get_channel(log_channel_id)
        if isinstance(channel, discord.TextChannel):
            embed = discord.Embed(title=f"🛠️ 레일라 업데이트 ({version})", description=body, color=0x5B8CFF)
            try:
                await channel.send(embed=embed)
            except discord.HTTPException as e:
                print(f"⚠️ 업데이트 로그 전송 실패 (guild={guild.id}): {e}")

        update_guild_settings(guild.id, last_announced_version=version)


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")

    async with bot:
        for extension in INITIAL_EXTENSIONS:
            await bot.load_extension(extension)
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 봇 종료")
