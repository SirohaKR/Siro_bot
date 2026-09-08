# -*- coding: utf-8 -*-
# 시로냥 봇 부트스트랩 — 메이플스토리 길드 관리용 (역할 지정 / 채널 관리 담당)
#
# 이 파일 하나로 봇을 켜고 끈다. 실제 기능은 cogs/roles.py, cogs/channels.py에 나눠져 있고,
# 이 파일은 그 기능들을 불러와서(load_extension) 디스코드에 접속시키는 역할만 한다.
#
# 참고: 역할/채널을 "무엇으로 설정할지"는 이 봇이 아니라 web/app.py(브라우저로 여는 설정
# 페이지)에서 관리한다. main.py는 그 설정을 읽어서 실제로 이모지 반응을 감시하고
# 음성채널을 자동 생성/삭제하는, 항상 켜져 있어야 하는 "실행" 담당이다.

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()  # .env 파일에 적어둔 DISCORD_TOKEN 같은 값을 읽어온다.

TOKEN = os.getenv("DISCORD_TOKEN")

# 새 기능(cog)을 추가할 때는 여기에 모듈 경로만 한 줄 추가하면 된다.
INITIAL_EXTENSIONS = [
    "cogs.roles",
    "cogs.channels",
    "cogs.info",  # "/설정" 명령어 — 웹 설정 페이지 주소를 알려줌
]

# Intents(인텐트) = 봇이 디스코드로부터 받을 이벤트의 종류를 미리 선언하는 것.
# members: 서버 멤버 정보를 읽고 역할을 부여/제거하기 위해 필요 (디스코드 개발자 포털에서
#          "SERVER MEMBERS INTENT"도 함께 켜야 한다. README.md 참고)
# voice_states: 누가 음성채널에 들어오고 나가는지 감지(파티모집 채널 기능)하기 위해 필요.
# 이모지 반응(reactions) 감지는 특별히 켤 필요 없는 "기본 인텐트"라 default()에 이미 포함되어 있다.
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print("\n" + "=" * 40)
    print(f"봇 이름: {bot.user.name}")
    print(f"봇 ID: {bot.user.id}")
    print("✅ 시로냥 봇 실행/연결 완료")

    try:
        synced = await bot.tree.sync()
        print(f"🌳 슬래시 명령어 동기화 완료 ({len(synced)}개)")
    except Exception as e:
        print(f"⚠️ 슬래시 명령어 동기화 실패: {e}")

    print("=" * 40 + "\n")


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
