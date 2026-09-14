# -*- coding: utf-8 -*-
"""
채널 관리 담당 Cog.

"어떤 음성채널을 허브로 쓸지, 새로 만들어지는 채널 이름을 어떻게 지을지"는
명령어가 아니라 웹 설정 페이지(web/app.py)에서 관리자가 정한다(기존 채널을
고르거나, 페이지에서 새로 만들 수 있다). 허브는 원하는 만큼 여러 개 만들 수
있다 (예: 이름별 파티 채널, 번호 매겨진 개인방, 자유 음성방 등). 이 파일은 그렇게
정해진 허브 채널들에 사람이 들어오고 나가는 것만 감시해서, 채널을 자동으로
만들고 지우는 역할만 한다.

동작 방식:
1. 누군가 허브 채널에 들어오면 -> 그 허브에 지정된 이름 규칙(name_template)대로
   이름을 지어서 새 음성채널을 만들고 그쪽으로 이동시킨다.
   - {user} 는 입장한 사람의 이름으로, {n} 은 그 허브에서 몇 번째로 만든 채널인지로
     바뀐다. 예) "{user}의 파티" -> "홍길동의 파티", "개인방 {n}" -> "개인방 4"
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
        voice_hubs: list = settings.get("voice_hubs", [])
        temp_channel_ids: list = settings.get("temp_voice_channel_ids", [])

        # 1) 허브 채널 중 하나에 새로 들어온 경우 -> 그 허브의 이름 규칙대로 채널을 만든다.
        if after.channel:
            hub = next((h for h in voice_hubs if h.get("id") == after.channel.id), None)
            if hub:
                hub["counter"] = hub.get("counter", 0) + 1
                name = hub.get("name_template", "{user}의 방").format(
                    user=member.display_name, n=hub["counter"]
                )[:100]  # 디스코드 채널 이름은 100자 제한
                new_channel = await guild.create_voice_channel(
                    name=name,
                    category=after.channel.category,
                    reason="음성 허브 입장으로 자동 생성",
                )
                await member.move_to(new_channel, reason="자동 생성된 채널로 이동")
                temp_channel_ids.append(new_channel.id)
                update_guild_settings(guild.id, voice_hubs=voice_hubs, temp_voice_channel_ids=temp_channel_ids)

        # 2) 봇이 만들어준 임시 채널에서 사람이 빠져나가 완전히 비었으면 -> 삭제.
        if before.channel and before.channel.id in temp_channel_ids:
            still_empty = len(before.channel.members) == 0
            if still_empty:
                await before.channel.delete(reason="빈 채널 자동 삭제")
                temp_channel_ids.remove(before.channel.id)
                update_guild_settings(guild.id, temp_voice_channel_ids=temp_channel_ids)


async def setup(bot: commands.Bot):
    await bot.add_cog(Channels(bot))
