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
   - {user} 는 입장한 사람의 이름으로 바뀐다.
   - {n} 은 번호로 바뀌는데, "지금 그 허브에서 살아있는 방들 중 비어있는 가장 작은
     번호"를 쓴다. 예를 들어 "개인방 1"이 있는 상태에서 하나 더 만들면 "개인방 2"가
     되고, "개인방 1"이 사라진 뒤에 새로 만들면 다시 "개인방 1"부터 채워진다
     (총 몇 번 만들었는지 계속 세는 게 아니라, 지금 몇 개나 떠 있는지를 본다).
   - 허브에 user_limit(최대 인원)이 정해져 있으면 새로 만드는 채널에도 그대로
     적용한다. 예) 1인 개인방 허브는 user_limit=1로 만들어서 디스코드가 알아서
     두 번째 사람은 못 들어오게 막아준다.
2. 봇이 만들어준 그 채널에 아무도 안 남으면 -> 자동으로 삭제한다.
"""
from __future__ import annotations

import discord
from discord.ext import commands

from core.settings_store import get_guild_settings, update_guild_settings


def _next_available_number(hub_id: int, temp_channels: list[dict]) -> int:
    """그 허브에서 지금 살아있는 채널들이 쓰고 있는 번호를 피해서, 빈 번호 중 가장
    작은 걸 돌려준다 (1, 2, 3 ... 순서로 채워나가고, 중간이 비면 그 자리부터 채움)."""
    used_numbers = {
        tc["number"] for tc in temp_channels if tc.get("hub_id") == hub_id and tc.get("number") is not None
    }
    n = 1
    while n in used_numbers:
        n += 1
    return n


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
        temp_channels: list = settings.get("temp_voice_channels", [])

        # 1) 허브 채널 중 하나에 새로 들어온 경우 -> 그 허브의 이름 규칙대로 채널을 만든다.
        if after.channel:
            hub = next((h for h in voice_hubs if h.get("id") == after.channel.id), None)
            if hub:
                template = hub.get("name_template") or "{user}의 방"
                number = _next_available_number(hub["id"], temp_channels) if "{n}" in template else None
                name = template.format(user=member.display_name, n=number if number is not None else "")[:100]

                new_channel = await guild.create_voice_channel(
                    name=name,
                    category=after.channel.category,
                    user_limit=hub.get("user_limit") or 0,  # 0 = 디스코드 기준 무제한
                    reason="음성 허브 입장으로 자동 생성",
                )
                await member.move_to(new_channel, reason="자동 생성된 채널로 이동")
                temp_channels.append({"channel_id": new_channel.id, "hub_id": hub["id"], "number": number})
                update_guild_settings(guild.id, temp_voice_channels=temp_channels)

        # 2) 봇이 만들어준 임시 채널에서 사람이 빠져나가 완전히 비었으면 -> 삭제.
        if before.channel:
            entry = next((tc for tc in temp_channels if tc["channel_id"] == before.channel.id), None)
            if entry and len(before.channel.members) == 0:
                await before.channel.delete(reason="빈 채널 자동 삭제")
                temp_channels.remove(entry)
                update_guild_settings(guild.id, temp_voice_channels=temp_channels)


async def setup(bot: commands.Bot):
    await bot.add_cog(Channels(bot))
