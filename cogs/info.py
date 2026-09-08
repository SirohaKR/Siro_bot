# -*- coding: utf-8 -*-
"""
잡다한 편의 명령어를 담는 Cog. 지금은 "/설정" 하나뿐이다.

/설정 명령어는 관리자가 웹 설정 페이지(web/app.py) 주소를 매번 따로 기억하거나
찾아보지 않아도, 디스코드에서 바로 받아볼 수 있게 해주는 지름길이다. 이 링크에는
페이지 접속용 비밀 토큰(WEB_ADMIN_TOKEN)이 그대로 포함되므로, 아무나 보면 안 된다.
그래서 답장은 명령어를 사용한 사람에게만 보이게(ephemeral) 하고, 사용 권한도
"역할 관리" 권한이 있는 사람으로 제한한다.
"""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="설정", description="[관리자] 시로냥 웹 설정 페이지 주소를 알려줍니다.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def settings_url(self, interaction: discord.Interaction):
        base_url = os.getenv("WEB_PUBLIC_URL")
        admin_token = os.getenv("WEB_ADMIN_TOKEN")

        if not base_url:
            await interaction.response.send_message(
                "⚠️ 아직 설정 페이지 주소가 등록되지 않았습니다. .env의 WEB_PUBLIC_URL 값을 채워주세요.",
                ephemeral=True,
            )
            return

        url = f"{base_url.rstrip('/')}/?token={admin_token}" if admin_token else base_url
        await interaction.response.send_message(
            f"🔧 시로냥 설정 페이지\n{url}\n(다른 사람에게 공유하지 마세요 — 이 링크만 있으면 누구나 설정을 바꿀 수 있어요)",
            ephemeral=True,
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "⚠️ 이 명령어는 '역할 관리' 권한이 있어야 사용할 수 있습니다.", ephemeral=True
            )
            return
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
