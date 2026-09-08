# -*- coding: utf-8 -*-
"""
채널 관리 담당 Cog.

"어떤 음성채널을 파티모집 허브로 쓸지"는 명령어가 아니라 웹 설정 페이지(web/app.py)에서
관리자가 정한다(기존 채널을 고르거나, 페이지에서 새로 만들 수 있다). 이 파일은 그렇게
정해진 허브 채널에 사람이 들어오고 나가는 것만 감시해서, 개인 음성채널을 자동으로
만들고 지우는 역할만 한다.

동작 방식:
1. 누군가 허브 채널(예: "➕ 파티 모집")에 들어오면 -> 그 사람 이름으로 된 새 음성채널을
   만들어서 그쪽으로 이동시킨다.
2. 봇이 만들어준 그 채널에 아무도 안 남으면 -> 자동으로 삭제한다.
"""
from __future__ import annotations

import discord
from discord.ext import commands

from core.settings_store import get_guild_settings, update_guild_settings


class Channels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        guild = member.guild
        settings = get_guild_settings(guild.id)
        hub_channel_id = settings.get("hub_voice_channel_id")
        temp_channel_ids: list = settings.get("temp_voice_channel_ids", [])

        # 1) 허브 채널에 새로 들어온 경우 -> 개인 채널을 만들어서 그쪽으로 이동시킨다.
        if hub_channel_id and after.channel and after.channel.id == hub_channel_id:
            new_channel = await guild.create_voice_channel(
                name=f"{member.display_name}의 파티",
                category=after.channel.category,
                reason="파티모집 허브 입장으로 자동 생성",
            )
            await member.move_to(new_channel, reason="개인 파티 채널로 이동")
            temp_channel_ids.append(new_channel.id)
            update_guild_settings(guild.id, temp_voice_channel_ids=temp_channel_ids)

        # 2) 봇이 만들어준 임시 채널에서 사람이 빠져나가 완전히 비었으면 -> 삭제.
        if before.channel and before.channel.id in temp_channel_ids:
            still_empty = len(before.channel.members) == 0
            if still_empty:
                await before.channel.delete(reason="파티 채널이 비어서 자동 삭제")
                temp_channel_ids.remove(before.channel.id)
                update_guild_settings(guild.id, temp_voice_channel_ids=temp_channel_ids)


async def setup(bot: commands.Bot):
    await bot.add_cog(Channels(bot))
