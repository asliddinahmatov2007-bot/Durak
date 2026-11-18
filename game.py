import random, html, time
R = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
S = "♠♥♦♣"

def rk(c): return R.index(c[:-1])
def beats(a, d, trump):
    return rk(d) > rk(a) if a[-1] == d[-1] else d[-1] == trump
def sort_cards(cs): return sorted(cs, key=lambda c: (S.index(c[-1]), rk(c)))

class Game:
    def __init__(s, chat, team):
        s.chat, s.team = chat, team
        s.ids, s.names = [], []
        s.started, s.mid = False, None
        s.turn_mid = s.pin_mid = None
        s.place = []

    def seat(s, uid): return s.ids.index(uid) if uid in s.ids else None

    def start(s):
        z = list(zip(s.ids, s.names)); random.shuffle(z)   # o'rindiqlar: 0&2 va 1&3 sherik
        s.ids, s.names = [a for a, _ in z], [b for _, b in z]
        s.n = len(s.ids)
        s.deck = [r + su for r in R for su in S]; random.shuffle(s.deck)
        s.trump = s.deck[0][-1]
        s.hands = [[s.deck.pop() for _ in range(6)] for _ in range(s.n)]
        s.got = [6] * s.n
        s.t0 = time.time()
        tr = [(rk(c), i) for i, h in enumerate(s.hands) for c in h if c[-1] == s.trump]
        s.att = min(tr)[1] if tr else 0
        s.out, s.started = set(), True
        s.new_round()

    def nxt(s, i):
        for k in range(1, s.n + 1):
            j = (i + k) % s.n
            if j not in s.out: return j

    def new_round(s):
        s.dfn = s.nxt(s.att); s.table = []
        s.limit = min(6, len(s.hands[s.dfn]))

    def und(s): return [t for t in s.table if t[1] is None]
    def can_take(s, seat): return seat == s.dfn and bool(s.und())
    def can_bito(s, seat):
        return seat != s.dfn and seat not in s.out and bool(s.table) and not s.und()

    def legal(s, seat):
        h = s.hands[seat]
        if seat == s.dfn:
            u = s.und()
            return [c for c in h if beats(u[0][0], c, s.trump)] if u else []
        if seat in s.out or len(s.table) >= s.limit or s.und(): return []
        if not s.table: return list(h) if seat == s.att else []
        ranks = {c[:-1] for t in s.table for c in t if c}
        return [c for c in h if c[:-1] in ranks]

    def play(s, seat, card):
        if card not in s.legal(seat): return False
        s.hands[seat].remove(card)
        if seat == s.dfn: s.und()[0][1] = card
        else: s.table.append([card, None])
        return True

    def finish(s, took):
        cards = [c for t in s.table for c in t if c]
        if took:
            s.hands[s.dfn] += cards
            s.got[s.dfn] += len(cards)
        order = [(s.att + k) % s.n for k in range(s.n)]
        order = [x for x in order if x != s.dfn] + [s.dfn]
        for x in order:
            while len(s.hands[x]) < 6 and s.deck:
                s.hands[x].append(s.deck.pop()); s.got[x] += 1
        for x in range(s.n):
            if not s.hands[x] and not s.deck and x not in s.out:
                s.out.add(x); s.place.append(x)
        res = s.result()
        if res: return s.summary(res)
        s.att = s.nxt(s.dfn) if took or s.dfn in s.out else s.dfn
        s.new_round()

    def result(s):
        alive = [i for i in range(s.n) if i not in s.out]
        e = html.escape
        if s.team:
            done = [t for t in (0, 1) if {t, t + 2} <= s.out]
            if len(done) == 2: return "🤝 Durang!"
            if done:
                t = done[0]
                return f"🏆 Jamoa {t+1} yutdi: {e(s.names[t])} va {e(s.names[t+2])}"
        else:
            if not alive: return "🤝 Durang!"
            if len(alive) == 1:
                w = f"🏆 {e(s.names[s.place[0]])} yutdi!\n" if s.place else ""
                return f"{w}🤡 Durak: {e(s.names[alive[0]])}"

    def summary(s, head):
        lines = "\n".join(
            f"{html.escape(s.names[i])}{' [J' + str(i % 2 + 1) + ']' if s.team else ''} ({len(s.hands[i])} / {s.got[i]})"
            for i in range(s.n))
        mins = max(1, round((time.time() - s.t0) / 60))
        return f"{head}\n\n{lines}\n\n⏳ O'yin vaqti: {mins} daqiqa"

    def render(s, bot):
        t = f"🃏 <b>Durak{' · Jamoaviy' if s.team else ''}</b>\nKozir: <b>{s.trump}</b> · To'plam: {len(s.deck)}\n"
        t += "Stol: " + (", ".join(f"{a}→{d or '?'}" for a, d in s.table) or "bo'sh") + "\n\n"
        for i in range(s.n):
            tag = " ✅ chiqdi" if i in s.out else " ⚔️ hujum" if i == s.att else " 🛡 himoya" if i == s.dfn else ""
            tm = f" [J{i%2+1}]" if s.team else ""
            t += f"{html.escape(s.names[i])}{tm}: {len(s.hands[i])} karta{tag}\n"
        return t + f"\nKarta tashlash: guruhda @{bot} deb yozing"
