import os, asyncio, html
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineQuery, ChosenInlineResult, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle,
    InputTextMessageContent, InlineQueryResultsButton)
from game import Game, sort_cards

bot, dp = Bot(os.environ["BOT_TOKEN"]), Dispatcher()
games, where, BOT, BOT_ID = {}, {}, "", 0

def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])
JOIN = kb([[("➕ Qo'shilish", "j")]])
PLAY = kb([[("🃏 Kartalarim", "h")], [("🛡 Olaman", "t"), ("✅ Bito", "b")]])

def lobby(g):
    names = "\n".join("• " + html.escape(n) for n in g.names)
    return f"🃏 <b>Durak{' · Jamoaviy' if g.team else ''}</b>\nO'yinchilar ({len(g.ids)}/4):\n{names}"

async def edit(g, text, markup=PLAY):
    try:
        await bot.edit_message_text(text, chat_id=g.chat, message_id=g.mid, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass

def drop(g):
    for u in g.ids: where.pop(u, None)
    games.pop(g.chat, None)

async def new(m: Message, team):
    if m.chat.type == "private": return await m.answer("Meni guruhga qo'shib, shu yerda /durak yozing.")
    if m.chat.id in games: return await m.answer("Bu guruhda o'yin bor. To'xtatish: /stop")
    g = games[m.chat.id] = Game(m.chat.id, team)
    sent = await m.answer(lobby(g), reply_markup=JOIN, parse_mode="HTML")
    g.mid = sent.message_id

@dp.message(Command("durak"))
async def c1(m: Message): await new(m, False)
@dp.message(Command("jamoa"))
async def c2(m: Message): await new(m, True)

@dp.message(Command("stop"))
async def stop(m: Message):
    g = games.get(m.chat.id)
    if g: drop(g); await m.answer("O'yin to'xtatildi.")

@dp.callback_query()
async def cb(q: CallbackQuery):
    g, u = games.get(q.message.chat.id), q.from_user
    if not g: return await q.answer("O'yin yo'q", show_alert=True)
    if q.data == "j":
        if g.started: return await q.answer("O'yin boshlangan")
        if u.id in where: return await q.answer("Siz allaqachon o'yindasiz", show_alert=True)
        g.ids.append(u.id); g.names.append(u.first_name); where[u.id] = g.chat
        if len(g.ids) < 4: return await edit(g, lobby(g), JOIN) or await q.answer()
        g.start(); await edit(g, g.render(BOT)); return await q.answer()
    s = g.seat(u.id)
    if s is None or not g.started: return await q.answer("Siz o'yinda emassiz", show_alert=True)
    if q.data == "h":
        return await q.answer(f"Kozir {g.trump}\n" + " ".join(sort_cards(g.hands[s])), show_alert=True)
    if q.data == "t":
        if not g.can_take(s): return await q.answer("Hozir olib bo'lmaydi", show_alert=True)
        res = g.finish(True)
    else:
        if not g.can_bito(s): return await q.answer("Hozir bito qilib bo'lmaydi", show_alert=True)
        res = g.finish(False)
    if res: drop(g); await edit(g, res, None)
    else: await edit(g, g.render(BOT))
    await q.answer()

@dp.inline_query()
async def iq(q: InlineQuery):
    g = games.get(where.get(q.from_user.id))
    cards = sort_cards(g.legal(g.seat(q.from_user.id))) if g and g.started else []
    res = [InlineQueryResultArticle(id=c, title=c, description="Tashlash", input_message_content=InputTextMessageContent(message_text=f"🃏 {c}")) for c in cards]
    kw = {} if res else {"button": InlineQueryResultsButton(text="Hozir karta tashlay olmaysiz", start_parameter="info")}
    await q.answer(res, cache_time=0, is_personal=True, **kw)

@dp.message(F.via_bot)
async def moved(m: Message):
    if m.via_bot.id != BOT_ID or not m.text or not m.text.startswith("🃏 "): return
    g = games.get(where.get(m.from_user.id))
    if g and g.started and g.play(g.seat(m.from_user.id), m.text[2:].strip()):
        await edit(g, g.render(BOT))
    try: await m.delete()
    except Exception: pass

async def main():
    global BOT, BOT_ID
    app = web.Application(); app.router.add_get("/", lambda _: web.Response(text="ok"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8000))).start()
    me = await bot.get_me(); BOT, BOT_ID = me.username, me.id
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

asyncio.run(main())
