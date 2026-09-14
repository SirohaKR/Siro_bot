# -*- coding: utf-8 -*-
"""
채팅에 이모티콘 딱 하나만 올라오면, 그걸 스티커만큼 큰 이미지로 다시 보여주는 Cog
("거지" 봇 등 여러 디스코드 봇에서 흔히 볼 수 있는 기능).

동작:
1. 커스텀 서버 이모지(<:이름:아이디>) 하나만 왔을 때 -> 디스코드 자체 CDN에서 그
   이모지의 원본 이미지를 가져와 크게 보여준다. (서버 이모지라 항상 존재가 보장됨)
2. 일반 유니코드 이모지(😀, ❤️, 🇰🇷, 👨‍👩‍👧‍👦 같은 것) 하나만 왔을 때 -> 오픈소스
   이모지 이미지 세트인 Twemoji에서 그 이모지에 해당하는 그림을 가져와 크게 보여준다.
   유니코드 이모지는 진짜 그림 파일이 따로 없어서(글자처럼 처리됨), 코드값(codepoint)을
   Twemoji 파일 이름 규칙대로 조합해서 이미지 주소를 만든다. ❤️처럼 "변형 선택자"가
   붙는 이모지는 그 값을 포함/제외한 두 가지 주소를 다 시도해본다.
3. 이모지가 여러 개거나 다른 글자와 섞여 있으면 그냥 둔다.

전체 서버, 모든 채널에서 항상 동작한다 (설정 페이지에서 켜고 끄는 기능 아님).
원본의 작은 이모지 메시지는 지우지 않고, 답장(reply) 형태로 큰 이미지를 새로 올린다.
"""
from __future__ import annotations

import re

import aiohttp
import discord
import emoji as emoji_lib
from discord.ext import commands

CUSTOM_EMOJI_RE = re.compile(r"^<(a?):(\w+):(\d+)>$")
TWEMOJI_BASE = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72"


def _twemoji_urls(text: str) -> list[str]:
    """이모지 하나를 Twemoji 이미지 주소 후보 목록으로 바꾼다."""
    codepoints = [f"{ord(ch):x}" for ch in text]
    with_fe0f = "-".join(codepoints)
    without_fe0f = "-".join(c for c in codepoints if c != "fe0f")

    urls = [f"{TWEMOJI_BASE}/{with_fe0f}.png"]
    if without_fe0f != with_fe0f:
        urls.append(f"{TWEMOJI_BASE}/{without_fe0f}.png")
    return urls


def _is_single_emoji(text: str) -> bool:
    matches = emoji_lib.emoji_list(text)
    return len(matches) == 1 and matches[0]["match_start"] == 0 and matches[0]["match_end"] == len(text)


class BigEmoji(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _first_working_url(self, urls: list[str]) -> str | None:
        """후보 이미지 주소 중, 실제로 접속되는 첫 번째 주소를 찾는다."""
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            return url
                except aiohttp.ClientError:
                    continue
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        content = message.content.strip()
        if not content:
            return

        custom_match = CUSTOM_EMOJI_RE.fullmatch(content)
        if custom_match:
            animated, _name, emoji_id = custom_match.groups()
            ext = "gif" if animated else "png"
            await self._post_big(message, f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}")
            return

        if _is_single_emoji(content):
            image_url = await self._first_working_url(_twemoji_urls(content))
            if image_url:
                await self._post_big(message, image_url)

    async def _post_big(self, message: discord.Message, image_url: str) -> None:
        embed = discord.Embed(color=0x5B8CFF)
        embed.set_image(url=image_url)
        try:
            await message.reply(embed=embed, mention_author=False)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(BigEmoji(bot))
