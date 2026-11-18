import os, asyncio, html
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineQuery, Message, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultPhoto, InlineQueryResultCachedSticker, InlineQueryResultsButton)
from game import Game, sort_cards
from cards import card_jpg, by_name, url_name

bot, dp = Bot(os.environ["BOT_TOKEN"]), Dispatcher()
games, where, BOT, BOT_ID = {}, {}, "", 0
BASE = (os.environ.get("BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")

SET = os.environ.get("STICKER_SET", "PlayingCards_Alexzhdanov")
ORDER = [r + s for r in ["6", "7", "8", "9", "10", "J", "Q"] for s in "♥♦♣♠"] + [r + s for r in ["K", "A"] for s in "♥♦♠♣"]
STK, UNQ = {}, {}   # karta -> file_id, file_unique_id -> karta

async def load_stickers():
    try:
        st = await bot.get_sticker_set(SET)
        cards = st.stickers[2:38]          # boshidagi 2 ta va oxirgi joker olinmaydi
        if len(cards) == 36:
            for c, s in zip(ORDER, cards):
                STK[c] = s.file_id; UNQ[s.file_unique_id] = c
    except Exception as e:
        print("Stikerlar yuklanmadi:", e)

def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])
JOIN = kb([[("➕ Qo'shilish", "j")]])
PLAY = kb([[("🃏 Kartalarim", "h")], [("🛡 Olaman", "t"), ("✅ Bito", "b")]])
def jk(g): return kb([[("➕ Qo'shilish", "j")]] + ([[("▶️ Boshlash", "s")]] if not g.team and len(g.ids) >= 2 else []))

def lobby(g):
    names = "\n".join("• " + html.escape(n) for n in g.names)
    hint = "4 kishi kerak" if g.team else "2-4 kishi (4 ta bo'lsa o'zi boshlanadi)"
    return f"🃏 <b>Durak{' · Jamoaviy' if g.team else ''}</b>\nO'yinchilar ({len(g.ids)}/4):\n{names}\n\n{hint}"

async def edit(g, text, markup=PLAY):
    try:
        await bot.edit_message_text(text, chat_id=g.chat, message_id=g.mid, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass

async def safe(coro):
    try: return await coro
    except Exception: return None

def turn_info(g):
    seat, act = (g.dfn, "himoya qiling") if g.und() else (g.att, "hujum qiling" + (" (yoki Bito)" if g.table else ""))
    return f'<a href="tg://user?id={g.ids[seat]}">{html.escape(g.names[seat])}</a>, {act}'

def turn_kb(g):
    rows = [[InlineKeyboardButton(text="🃏 Kartalarni ko'rish", switch_inline_query_current_chat="")]]
    if g.und(): rows.append([InlineKeyboardButton(text="🛡 Olaman", callback_data="t")])
    elif g.table: rows.append([InlineKeyboardButton(text="✅ Bito", callback_data="b")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def turn(g):
    if g.turn_mid: await safe(bot.delete_message(g.chat, g.turn_mid))
    m = await safe(bot.send_message(g.chat, turn_info(g), reply_markup=turn_kb(g), parse_mode="HTML"))
    g.turn_mid = m.message_id if m else None

async def pin_trump(g):
    c = g.deck[0]
    if c in STK: await safe(bot.send_sticker(g.chat, STK[c]))
    else: await safe(bot.send_photo(g.chat, BufferedInputFile(card_jpg(c), "k.jpg")))
    t = await safe(bot.send_message(g.chat, f"🃏 Kozir: <b>{g.trump}</b>", parse_mode="HTML"))
    if t:
        g.pin_mid = t.message_id
        await safe(bot.pin_chat_message(g.chat, t.message_id, disable_notification=True))

async def begin(g):
    g.start()
    await edit(g, g.render(BOT))
    await pin_trump(g)
    await turn(g)

async def after(g, res=None):
    if res:
        await edit(g, res, None)
        await cleanup(g)
    else:
        await edit(g, g.render(BOT))
        await turn(g)

async def cleanup(g):
    if g.turn_mid: await safe(bot.delete_message(g.chat, g.turn_mid))
    if g.pin_mid: await safe(bot.unpin_chat_message(g.chat, g.pin_mid))
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
    if g: await cleanup(g); await m.answer("O'yin to'xtatildi.")

@dp.callback_query()
async def cb(q: CallbackQuery):
    g, u = games.get(q.message.chat.id), q.from_user
    if not g: return await q.answer("O'yin yo'q", show_alert=True)
    if q.data == "j":
        if g.started: return await q.answer("O'yin boshlangan")
        if u.id in where: return await q.answer("Siz allaqachon o'yindasiz", show_alert=True)
        g.ids.append(u.id); g.names.append(u.first_name); where[u.id] = g.chat
        await q.answer()
        if len(g.ids) < 4: return await edit(g, lobby(g), jk(g))
        return await begin(g)
    if q.data == "s":
        if g.started or g.team or u.id not in g.ids or len(g.ids) < 2:
            return await q.answer("Boshlab bo'lmaydi", show_alert=True)
        await q.answer()
        return await begin(g)
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
    await q.answer()
    await after(g, res)

def photo(c):
    u = f"{BASE}/c/{url_name(c)}.jpg"
    return InlineQueryResultPhoto(id=c, photo_url=u, thumbnail_url=u, photo_width=320, photo_height=448, caption=f"🃏 {c}")

def result(c):
    if c in STK: return InlineQueryResultCachedSticker(id=url_name(c), sticker_file_id=STK[c])
    return photo(c)

@dp.inline_query()
async def iq(q: InlineQuery):
    g = games.get(where.get(q.from_user.id))
    cards = sort_cards(g.legal(g.seat(q.from_user.id))) if g and g.started else []
    res = [result(c) for c in cards]
    kw = {} if res else {"button": InlineQueryResultsButton(text="Hozir karta tashlay olmaysiz", start_parameter="info")}
    await q.answer(res, cache_time=0, is_personal=True, **kw)

@dp.message(F.via_bot)
async def moved(m: Message):
    if m.via_bot.id != BOT_ID: return
    c = UNQ.get(m.sticker.file_unique_id) if m.sticker else None
    if not c:
        txt = m.caption or m.text or ""
        if not txt.startswith("🃏 "): return
        c = txt[2:].strip()
    g = games.get(where.get(m.from_user.id))
    if g and g.started and g.play(g.seat(m.from_user.id), c):
        await after(g)

@dp.message(Command("tekshir"))
async def check(m: Message):
    if not STK: return await m.answer("Stikerlar yuklanmadi, kartalar rasm bilan ishlaydi.")
    for i in range(0, 36, 6):
        for c in ORDER[i:i + 6]:
            await m.answer_sticker(STK[c]); await asyncio.sleep(0.4)
        await m.answer(" ".join(ORDER[i:i + 6]))

async def card_img(req):
    try: return web.Response(body=by_name(req.match_info["n"]), content_type="image/jpeg")
    except Exception: return web.Response(status=404)

async def main():
    global BOT, BOT_ID
    app = web.Application()
    app.router.add_get("/", lambda _: web.Response(text="ok"))
    app.router.add_get("/c/{n}.jpg", card_img)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8000))).start()
    me = await bot.get_me(); BOT, BOT_ID = me.username, me.id
    await load_stickers()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

asyncio.run(main())
