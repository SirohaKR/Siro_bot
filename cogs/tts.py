# -*- coding: utf-8 -*-
"""
텍스트채널에 쓴 글을 그 사람이 있는 음성채널에서 소리로 읽어주는 Cog (카톡 스타일 TTS).

"어느 텍스트채널을 TTS용으로 쓸지, 어떤 목소리를 쓸지"는 웹 설정 페이지(web/app.py)의
"🗣️ TTS" 페이지에서 정한다. 이 파일은 그 채널에 올라온 메시지를 감시해서, 글쓴이가
지금 들어가있는 음성채널에 봇을 데려가 읽어주는 실제 동작만 한다.

여러 메시지가 짧은 시간에 연달아 올라와도 소리가 겹치지 않도록, 서버(길드)마다
읽어야 할 메시지를 큐에 쌓아두고 백그라운드 작업이 하나씩 순서대로 재생한다.
"""
from __future__ import annotations

import asyncio
import os
import tempfile

import discord
import edge_tts
from discord.ext import commands

from core.settings_store import get_guild_settings

MAX_TEXT_LENGTH = 300  # 너무 긴 메시지가 음성채널을 오래 독점하지 않도록 자른다.
DEFAULT_VOICE = "ko-KR-SunHiNeural"


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
            await edge_tts.Communicate(text, voice_name).save(path)

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

        settings = get_guild_settings(message.guild.id)
        tts = settings.get("tts") or {}
        if not tts.get("channel_id") or message.channel.id != tts["channel_id"]:
            return

        voice_state = message.author.voice
        if voice_state is None or voice_state.channel is None:
            return  # 음성채널에 없으면 읽어줄 곳이 없으니 무시.

        voice_name = tts.get("voice") or DEFAULT_VOICE
        await self._queue_for(message.guild.id).put((voice_state.channel, text[:MAX_TEXT_LENGTH], voice_name))

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
