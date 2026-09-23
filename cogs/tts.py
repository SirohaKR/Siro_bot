# -*- coding: utf-8 -*-
"""
텍스트채널에 쓴 글을 그 사람이 있는 음성채널에서 소리로 읽어주는 Cog (카톡 스타일 TTS).

"어느 텍스트채널을 TTS용으로 쓸지, 어떤 목소리를 기본으로 쓸지"는 웹 설정 페이지
(web/app.py)의 "🗣️ TTS" 페이지에서 관리자가 정한다. 그와 별개로, 길드원 각자가
자기 메시지를 읽을 때만 쓸 개인 목소리를 정할 수도 있다 (개인 설정이 없으면 서버
기본값을 쓴다) — 목소리가 워낙 많아서(타입캐스트만 약 600개) 디스코드 명령어
선택지로는 다 담을 수 없어, 직접 고르는 건 웹의 "내 목소리 설정" 페이지에서 하고,
"/목소리설정" 명령어는 그 페이지 주소만 알려주는 역할만 한다. 이 파일은 실제로
채널을 감시해서 읽어주는 동작과, 그 안내 명령어를 담당한다.

여러 메시지가 짧은 시간에 연달아 올라와도 소리가 겹치지 않도록, 서버(길드)마다
읽어야 할 메시지를 큐에 쌓아두고 백그라운드 작업이 하나씩 순서대로 재생한다.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile

import discord
import emoji as emoji_lib
from discord import app_commands
from discord.ext import commands

from core.settings_store import get_guild_settings
from core.tts_engine import synthesize
from core.tts_voices import DEFAULT_VOICE

MAX_TEXT_LENGTH = 300  # 너무 긴 메시지가 음성채널을 오래 독점하지 않도록 자른다.

_CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")


def _is_emoji_only(text: str) -> bool:
    """이모티콘(서버 커스텀 + 유니코드)만 있고 읽을 만한 글자가 없는 메시지인지 확인한다.

    이런 메시지는 cogs/big_emoji.py가 이미 크게 키운 이미지로 대신 보여주고 있어서,
    TTS로 또 "이모지" 같은 걸 읽어주면 어색하다. 이모지를 다 떼어내고도 남는 글자가
    있으면(예: "ㅋㅋ😂") 그 부분은 정상적으로 읽어준다.
    """
    without_custom = _CUSTOM_EMOJI_RE.sub("", text)
    without_emoji = emoji_lib.replace_emoji(without_custom, replace="")
    return without_emoji.strip() == ""


class Tts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._queues: dict[int, asyncio.Queue] = {}

    def _queue_for(self, guild_id: int) -> asyncio.Queue:
        """서버별 재생 대기열. 처음 쓰이는 순간 그 큐를 처리할 백그라운드 작업도 같이 띄운다."""
        if guild_id not in self._queues:
            queue: asyncio.Queue = asyncio.Queue()
            self._queues[guild_id] = queue
            self.bot.loop.create_task(self._worker(guild_id, queue))
        return self._queues[guild_id]

    async def _worker(self, guild_id: int, queue: asyncio.Queue) -> None:
        while True:
            voice_channel, text, voice_name = await queue.get()
            try:
                await self._speak(voice_channel, text, voice_name)
            except Exception as e:
                print(f"⚠️ TTS 재생 중 오류 (guild={guild_id}): {e}")
            finally:
                queue.task_done()

    async def _speak(self, voice_channel: discord.VoiceChannel, text: str, voice_name: str) -> None:
        guild = voice_channel.guild
        vc = guild.voice_client

        if vc is None:
            vc = await voice_channel.connect()
        elif vc.channel.id != voice_channel.id:
            await vc.move_to(voice_channel)

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            audio_bytes = await synthesize(text, voice_name)
            with open(path, "wb") as f:
                f.write(audio_bytes)

            done = asyncio.Event()

            def _after(_error, loop=self.bot.loop):
                # discord.py는 재생이 끝나면 이 콜백을 별도 스레드에서 부르므로,
                # 이벤트 루프 쪽 Event는 스레드 안전한 방법으로 세팅해야 한다.
                loop.call_soon_threadsafe(done.set)

            vc.play(discord.FFmpegPCMAudio(path), after=_after)
            await done.wait()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        text = message.content.strip()
        if not text:
            return  # 이미지만 올리거나 빈 메시지면 읽을 게 없다.
        if _is_emoji_only(text):
            return  # 이모티콘만 있는 메시지는 big_emoji.py가 크게 보여주니 TTS로는 안 읽는다.

        settings = get_guild_settings(message.guild.id)
        tts = settings.get("tts") or {}
        if not tts.get("channel_id") or message.channel.id != tts["channel_id"]:
            return

        voice_state = message.author.voice
        if voice_state is None or voice_state.channel is None:
            return  # 음성채널에 없으면 읽어줄 곳이 없으니 무시.

        # 개인 목소리 설정("/목소리설정")이 있으면 그걸 우선 쓰고, 없으면 서버 기본값을 쓴다.
        user_voices: dict = settings.get("tts_user_voices", {})
        voice_name = user_voices.get(str(message.author.id)) or tts.get("voice") or DEFAULT_VOICE
        await self._queue_for(message.guild.id).put((voice_state.channel, text[:MAX_TEXT_LENGTH], voice_name))

    @app_commands.command(name="목소리설정", description="내 TTS 목소리를 개인적으로 정할 수 있는 웹페이지 주소를 알려줍니다.")
    async def set_my_voice(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("⚠️ 서버 안에서만 쓸 수 있는 명령어예요.", ephemeral=True)
            return

        base_url = os.getenv("WEB_PUBLIC_URL")
        if not base_url:
            await interaction.response.send_message(
                "⚠️ 아직 설정 페이지 주소가 등록되지 않았습니다. (.env의 WEB_PUBLIC_URL 확인)",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎙️ 내 목소리 설정하러 가기\n{base_url.rstrip('/')}/my-voice\n"
            "디스코드로 로그인한 뒤, 원하는 목소리를 검색해서 고르면 앞으로 제 메시지를 그 목소리로 읽어줘요.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """봇 혼자 음성채널에 남으면 자동으로 나간다."""
        if member.bot:
            return
        vc = member.guild.voice_client
        if vc is None or not before.channel or before.channel.id != vc.channel.id:
            return
        if not any(not m.bot for m in vc.channel.members):
            await vc.disconnect()


async def setup(bot: commands.Bot):
    await bot.add_cog(Tts(bot))
