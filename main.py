import time
import os, asyncio, html
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineQuery, Message, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultPhoto, InlineQueryResultCachedSticker, InlineQueryResultArticle,
    InputTextMessageContent, ChosenInlineResult, InlineQueryResultsButton)
from game import Game, sort_cards
from liars import LGame, RUS
from cards import card_jpg, by_name, url_name

bot, dp = Bot(os.environ["BOT_TOKEN"]), Dispatcher()
games, where, BOT, BOT_ID = {}, {}, "", 0
BASE = (os.environ.get("BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")

SET = os.environ.get("STICKER_SET", "Durakkarta_bot_by_fStikBot")
ORDER = [r + s for s in "♥♦♣♠" for r in ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]]
STK, UNQ, LUNQ, RFID = {}, {}, {}, {}   # karta->fid, uid->karta, uid->daraja, daraja->fid
BACK = None

async def load_stickers():
    global BACK
    try:
        st = await bot.get_sticker_set(SET)
        cards = st.stickers[1:37]          # 0: karta orqasi, 37: joker
        BACK = st.stickers[0].file_id
        if len(cards) == 36:
            for c, s in zip(ORDER, cards):
                STK[c] = s.file_id; UNQ[s.file_unique_id] = c
                if c[-1] == "♥" and c[:-1] in ("K", "Q", "A"):
                    LUNQ[s.file_unique_id] = c[:-1]; RFID[c[:-1]] = s.file_id
        if len(st.stickers) >= 38:
            j = st.stickers[37]
            LUNQ[j.file_unique_id] = "J"; RFID["J"] = j.file_id
    except Exception as e:
        print("Stikerlar yuklanmadi:", e)

def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])
JOIN = kb([[("➕ Qo'shilish", "j")]])
PLAY = kb([[("🃏 Kartalarim", "h")], [("🛡 Olaman", "t"), ("✅ Bito", "b")]])
def jk(g):
    team = getattr(g, "team", False)
    return kb([[("➕ Qo'shilish", "j")]] + ([[("▶️ Boshlash", "s")]] if not team and len(g.ids) >= 2 else []))

def lobby(g):
    names = "\n".join("• " + html.escape(n) for n in g.names)
    if isinstance(g, LGame):
        t, hint = "🎲 <b>Liar's Bar</b>", "2-4 kishi (4 ta bo'lsa o'zi boshlanadi)"
    else:
        t = f"🃏 <b>Durak{' · Jamoaviy' if g.team else ''}</b>"
        hint = "4 kishi kerak" if g.team else "2-4 kishi (4 ta bo'lsa o'zi boshlanadi)"
    return f"{t}\nO'yinchilar ({len(g.ids)}/4):\n{names}\n\n{hint}"

async def edit(g, text, markup=None):
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
    await edit(g, g.render(BOT), PLAY)
    await pin_trump(g)
    await turn(g)

async def after(g, res=None):
    if res:
        await edit(g, res, None)
        await cleanup(g)
    else:
        await edit(g, g.render(BOT), PLAY)
        await turn(g)

async def cleanup(g):
    if g.turn_mid: await safe(bot.delete_message(g.chat, g.turn_mid))
    pin = getattr(g, "pin_mid", None)
    if pin: await safe(bot.unpin_chat_message(g.chat, pin))
    for u in g.ids: where.pop(u, None)
    games.pop(g.chat, None)

async def new(m: Message, kind):
    if m.chat.type == "private": return await m.answer("Meni guruhga qo'shib, shu yerda buyruqni yozing.")
    if m.chat.id in games: return await m.answer("Bu guruhda o'yin bor. To'xtatish: /stop")
    g = games[m.chat.id] = LGame(m.chat.id) if kind == "liars" else Game(m.chat.id, kind == "team")
    sent = await m.answer(lobby(g), reply_markup=jk(g), parse_mode="HTML")
    g.mid = sent.message_id

@dp.message(Command("durak"))
async def c1(m: Message): await new(m, "durak")
@dp.message(Command("jamoa"))
async def c2(m: Message): await new(m, "team")
@dp.message(Command("liars"))
async def c3(m: Message): await new(m, "liars")

@dp.message(Command("stop"))
async def stop(m: Message):
    g = games.get(m.chat.id)
    if g: await cleanup(g); await m.answer("O'yin to'xtatildi.")

@dp.callback_query()
async def cb(q: CallbackQuery):
    if q.data == "x": return await q.answer("🂠 Yashirin karta")
    g, u = games.get(q.message.chat.id), q.from_user
    if not g: return await q.answer("O'yin yo'q", show_alert=True)
    if isinstance(g, LGame): return await lcb(q, g, u)
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
    if isinstance(g, LGame):
        s = g.seat(q.from_user.id)
        if not g.started or s is None or s not in g.alive:
            return await q.answer([], cache_time=0, is_personal=True)
        if g.cur != s or len(g.played) >= 3:
            return await q.answer([], cache_time=0, is_personal=True,
                button=InlineQueryResultsButton(text="Hozir karta tashlay olmaysiz", start_parameter="info"))
        res = [InlineQueryResultArticle(
                id=f"{i}-{r}", title=RUS[r], description="Yashirin tashlash",
                thumbnail_url=f"{BASE}/c/{'JOKER' if r == 'J' else r + 'H'}.jpg", thumbnail_width=320, thumbnail_height=448,
                input_message_content=InputTextMessageContent(message_text="🂠 Karta tashlandi"),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🂠", callback_data="x")]]))
               for i, r in enumerate(g.hands[s])]
        return await q.answer(res, cache_time=0, is_personal=True)
    cards = sort_cards(g.legal(g.seat(q.from_user.id))) if g and g.started else []
    res = [result(c) for c in cards]
    kw = {} if res else {"button": InlineQueryResultsButton(text="Hozir karta tashlay olmaysiz", start_parameter="info")}
    await q.answer(res, cache_time=0, is_personal=True, **kw)

def mention(g, i): return f'<a href="tg://user?id={g.ids[i]}">{html.escape(g.names[i])}</a>'

def lrender(g):
    rows = []
    for i in range(g.n):
        tag = "💀" if i not in g.alive else ("👉" if i == g.cur else "  ")
        k = len(g.hands[i]) if i in g.alive else 0
        rows.append(f"{tag} {html.escape(g.names[i])}: {k} karta")
    last = ""
    if g.last: last = f"\n\nOxirgi tashlov: {html.escape(g.names[g.last[0]])} ({len(g.last[1])} ta, yashirin)"
    return f"🎲 <b>Liar's Bar</b>\nStol kartasi: <b>{RUS[g.table]}</b>\n\n" + "\n".join(rows) + last

def lsummary(g):
    w = g.alive[0]
    left = "\n".join(f"{html.escape(g.names[i])}: {'💀 chiqdi' if i not in g.alive else 'tirik'}" for i in range(g.n))
    mins = max(1, round((time.time() - g.t0) / 60))
    return f"🏆 <b>{html.escape(g.names[w])}</b> yutdi!\n\n{left}\n\n⏳ O'yin vaqti: {mins} daqiqa"

async def lturn(g):
    if g.turn_mid: await safe(bot.delete_message(g.chat, g.turn_mid))
    if g.played:
        txt = f"{mention(g, g.cur)}, tashlandi: {len(g.played)}/3. Yana qo'shing yoki ✅ Tugatdim"
        rows = [[("✅ Tugatdim", "e")]]
    elif g.last:
        txt = f"{mention(g, g.cur)}, karta tashlang (1-3) yoki 🗿 Yolg'onchi!"
        rows = [[("🗿 Yolg'onchi!", "c")]]
    else:
        txt = f"{mention(g, g.cur)}, karta tashlang"
        rows = []
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🃏 Karta tanlash", switch_inline_query_current_chat="")]]
        + [[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])
    m = await safe(bot.send_message(g.chat, txt, reply_markup=markup, parse_mode="HTML"))
    g.turn_mid = m.message_id if m else None

async def lround(g):
    await safe(bot.send_message(g.chat, f"🔄 Yangi raund! Stol kartasi: <b>{RUS[g.table]}</b>", parse_mode="HTML"))

async def lbegin(g):
    g.start()
    await edit(g, lrender(g))
    await lround(g)
    await lturn(g)

async def lclaim(g, seat, n):
    if g.turn_mid: await safe(bot.delete_message(g.chat, g.turn_mid))
    row = [InlineKeyboardButton(text="🤡 Yolg'onchi", callback_data="c")]
    if g.hands[g.cur]: row.append(InlineKeyboardButton(text="🥰 Ishondim", callback_data="i"))
    txt = (f"{mention(g, seat)} {n} ta karta tanladi va deydi: <b>{RUS[g.table]}</b>\n"
           f"{mention(g, g.cur)}, siz nima deysiz?")
    m = await safe(bot.send_message(g.chat, txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[row]), parse_mode="HTML"))
    g.turn_mid = m.message_id if m else None

async def lend(g, seat):
    n = g.end(seat)
    if n is None: return False
    await lclaim(g, seat, n)
    await edit(g, lrender(g))
    return True

async def lchallenge(g, seat):
    r = g.challenge(seat)
    if r is None: return False
    cards, truthful, liar, loser = r
    for c in cards:
        if c in RFID: await safe(bot.send_sticker(g.chat, RFID[c]))
    verdict = "hammasi rost ✅" if truthful else "yolg'on! ❌"
    await safe(bot.send_message(g.chat, f"👀 Ochildi: {len(cards)} ta karta, {verdict}"))
    dead, p = g.spin(loser)
    res = f"🔫 {mention(g, loser)} revolver aylantiradi ({round(p * 100)}% ehtimol): " + ("💥 o'ldi, o'yindan chiqdi" if dead else "😮‍💨 omon qoldi")
    await safe(bot.send_message(g.chat, res, parse_mode="HTML"))
    if len(g.alive) == 1:
        await edit(g, lsummary(g))
        await cleanup(g)
        return True
    g.new_round(loser)
    await edit(g, lrender(g))
    await lround(g)
    await lturn(g)
    return True

async def lcb(q, g, u):
    if q.data == "j":
        if g.started: return await q.answer("O'yin boshlangan")
        if u.id in where: return await q.answer("Siz allaqachon o'yindasiz", show_alert=True)
        g.ids.append(u.id); g.names.append(u.first_name); where[u.id] = g.chat
        await q.answer()
        if len(g.ids) < 4: return await edit(g, lobby(g), jk(g))
        return await lbegin(g)
    if q.data == "s":
        if g.started or u.id not in g.ids or len(g.ids) < 2:
            return await q.answer("Boshlab bo'lmaydi", show_alert=True)
        await q.answer(); return await lbegin(g)
    s = g.seat(u.id)
    if s is None or not g.started: return await q.answer("Siz o'yinda emassiz", show_alert=True)
    if s not in g.alive: return await q.answer("Siz o'yindan chiqqansiz", show_alert=True)
    if q.data == "e":
        if not await lend(g, s): return await q.answer("Hozir tugatib bo'lmaydi", show_alert=True)
        return await q.answer()
    if q.data == "c":
        if not await lchallenge(g, s): return await q.answer("Hozir yolg'onchi deb bo'lmaydi", show_alert=True)
        return await q.answer()
    if q.data == "i":
        if not g.trust(s): return await q.answer("Hozir ishonib bo'lmaydi", show_alert=True)
        await q.answer()
        await safe(bot.send_message(g.chat, f"🥰 {mention(g, s)} ishondi, navbat unga o'tdi", parse_mode="HTML"))
        await edit(g, lrender(g))
        return await lturn(g)
    await q.answer()

@dp.chosen_inline_result()
async def chosen(r: ChosenInlineResult):
    g = games.get(where.get(r.from_user.id))
    if not isinstance(g, LGame) or not g.started: return
    s = g.seat(r.from_user.id)
    rank = r.result_id.split("-", 1)[-1]
    if s is None or not g.play(s, rank):
        if r.inline_message_id:
            await safe(bot.edit_message_text("❌ Bu karta tashlanmadi", inline_message_id=r.inline_message_id))
        return
    if BACK: await safe(bot.send_sticker(g.chat, BACK))
    await lturn(g)

@dp.message(F.via_bot)
async def moved(m: Message):
    if m.via_bot.id != BOT_ID: return
    g0 = games.get(where.get(m.from_user.id))
    if isinstance(g0, LGame): return
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
