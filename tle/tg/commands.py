from __future__ import annotations

import asyncio
import logging
import random

from aiogram import F, Router, types
from aiogram.filters.command import Command
from aiogram.enums import ParseMode

from tle.util import codeforces_common as cf_common, codeforces_api as cf, handle_logic
from tle.util.telegram_common import (
    embed_alert,
    embed_success,
    hyperlink,
    wrap_placeholder,
)

logger = logging.getLogger(__name__)

router = Router()

# ---------------- Ping ----------------


@router.message(Command("ping"))
async def ping_handler(message: types.Message):
    await message.answer("Pong!")


# ---------------- User info ----------------


@router.message(Command("user"))
async def user_info_handler(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) == 1:
        await message.answer(f"Usage: /user {wrap_placeholder('handle')}")
        return

    handle = parts[1].strip()
    try:
        (user,) = await cf.user.info(handles=[handle])
    except Exception as e:  # noqa: BLE001
        await message.answer(embed_alert(str(e)))
        return

    desc = (
        f"{hyperlink(user.handle, user.url)}\n"
        f"Rating: {user.rating if user.rating is not None else 'Unrated'}"
    )
    await message.answer(embed_success(desc), disable_web_page_preview=True, parse_mode=ParseMode.HTML)


# ---------------- Handle logic ----------------


async def _verify_compile_error(handle: str, problem: cf.Problem) -> bool:
    """Return True if user submitted a CE to *problem* in last minute."""
    subs = await cf.user.status(handle=handle, count=5)
    return any(
        sub.problem.name == problem.name and sub.verdict == "COMPILATION_ERROR" for sub in subs
    )


async def handle_set_logic(message: types.Message, cf_handle: str):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Random easy problem for verification
    problems = [p for p in cf_common.cache2.problem_cache.problems if p.rating <= 1200]
    problem = random.choice(problems)

    await message.answer(
        embed_neutral := embed_success(
            f"Submit a compilation error to {hyperlink(problem.name, problem.url)} within 60 seconds to verify ownership."
        ),
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
    )

    await asyncio.sleep(60)

    if not await _verify_compile_error(cf_handle, problem):
        await message.answer(embed_alert("Verification failed. Please try again."))
        return

    try:
        user = await handle_logic.link_handle(user_id, chat_id, cf_handle)
    except handle_logic.HandleError as e:
        await message.answer(embed_alert(str(e)))
        return

    await message.answer(
        embed_success(f"Linked to {hyperlink(user.handle, user.url)}"),
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
    )



async def handle_set_handler(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(f"Usage: /handle_set {wrap_placeholder('codeforces_handle')}")
        return
    cf_handle = parts[1].strip()
    await handle_set_logic(message, cf_handle)


async def handle_get_handler(message: types.Message):
    target_user = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    cf_user = handle_logic.fetch_handle(target_user.id, message.chat.id)
    if not cf_user:
        await message.answer(embed_alert("Handle not set."))
        return
    rating = cf_user.rating if cf_user.rating is not None else "Unrated"
    desc = (
        f"<b>{target_user.full_name}</b> → {hyperlink(cf_user.handle, cf_user.url)} "
        f"(rating: {rating})"
    )
    await message.answer(embed_success(desc), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# Combined /handle command


def _is_handle_sub(message: types.Message, sub: str) -> bool:
    return message.text.split()[1:2] == [sub]


@router.message(Command("handle"))
async def handle_combined(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) == 1:
        await message.answer(
            f"Usage: /handle set {wrap_placeholder('handle')} or /handle get {wrap_placeholder('user')}"
        )
        return
    sub = parts[1].lower()
    if sub == "set":
        if len(parts) < 3:
            await message.answer(
                f"Usage: /handle set {wrap_placeholder('handle')}"
            )
            return
        await handle_set_logic(message, parts[2].strip())
    elif sub == "get":
        await handle_get_handler(message)
    else:
        await message.answer("Unknown subcommand. Use set/get.")


# Export

def get_router() -> Router:
    return router
