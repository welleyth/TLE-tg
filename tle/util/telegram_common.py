"""Utility helpers for Telegram bot interaction.

This mirrors a subset of functionality from `discord_common.py` but adapted for
aiogram / Telegram.  Telegram does not have rich embeds; instead we rely on
HTML formatting and, when necessary, media attachments.
"""
from __future__ import annotations

import asyncio
import functools
import html
import logging
import random
from typing import Callable, Type

from aiogram import Bot, types
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

_CF_COLORS = ("#FFCA1F", "#198BCC", "#FF2020")
_SUCCESS_GREEN = "#28A745"
_ALERT_AMBER = "#FFBF00"


def random_cf_color() -> str:
    return random.choice(_CF_COLORS)


def fmt_codeforces(text: str, color: str | None = None) -> str:
    """Wrap *text* with HTML `<b>` tag and prepend a colored square emoji.

    Purely cosmetic helper that tries to mimic embed colour coding.
    """
    # Square emoji to act as color indicator
    square = "\U0001F7E8"  # default yellow square
    return f"{square} <b>{html.escape(text)}</b>" if text else text


def embed_neutral(desc: str) -> str:
    return html.escape(desc)


def embed_success(desc: str) -> str:
    return fmt_codeforces(desc, _SUCCESS_GREEN)


def embed_alert(desc: str) -> str:
    return fmt_codeforces(desc, _ALERT_AMBER)


# ------------------------------------------------------------
# Error handling decorator (similar to discord_common.send_error_if)
# ------------------------------------------------------------


def send_error_if(*error_cls: Type[BaseException]) -> Callable:
    """Decorator for aiogram message handlers.

    If wrapped handler raises one of *error_cls*, send the error text to the
    chat instead of propagating.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(message: types.Message, *args, **kwargs):
            try:
                return await func(message, *args, **kwargs)
            except error_cls as e:  # type: ignore[misc]
                await safe_send(message, embed_alert(str(e)))
            except TelegramAPIError as api_exc:
                # Log unexpected telegram errors then re-raise so aiogram handles.
                logger.exception("Telegram API error during handler execution", exc_info=api_exc)
                raise

        return wrapper

    return decorator


async def safe_send(message: types.Message, text: str, **kwargs):
    """Send *text* to *message.chat* gracefully handling Flood/Retry limits."""

    # Flood-wait retry loop (basic exponential back-off)
    delay = 1
    while True:
        try:
            return await message.answer(text, parse_mode=types.ParseMode.HTML, **kwargs)
        except TelegramAPIError as e:
            if "Too Many Requests" in str(e):
                logger.warning("Hit flood limit – sleeping for %s seconds", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise

