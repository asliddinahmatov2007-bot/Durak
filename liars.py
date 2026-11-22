import random, time

RANKS = ["K", "Q", "A"]
RUS = {"K": "👑 Qirol", "Q": "👸 Dama", "A": "🅰️ Tuz", "J": "🃏 Joker"}

class LGame:
    def __init__(s, chat):
        s.chat = chat
        s.ids, s.names = [], []
        s.mid = s.turn_mid = None
        s.started = False
        s.n = 0
        s.t0 = time.time()

    def seat(s, uid): return s.ids.index(uid) if uid in s.ids else None

    def start(s):
        z = list(zip(s.ids, s.names)); random.shuffle(z)
        s.ids = [a for a, _ in z]; s.names = [b for _, b in z]
        s.n = len(s.ids)
        s.spins = [0] * s.n
        s.alive = list(range(s.n))
        s.started = True
        s.new_round(0)

    def nxt(s, i):
        for k in range(1, s.n + 1):
            j = (i + k) % s.n
            if j in s.alive: return j
        return i

    def new_round(s, starter):
        deck = ["K"] * 6 + ["Q"] * 6 + ["A"] * 6 + ["J"] * 2
        random.shuffle(deck)
        s.hands = [[] for _ in range(s.n)]
        for i in s.alive:
            s.hands[i] = [deck.pop() for _ in range(5)]
        s.table = random.choice(RANKS)
        s.cur = starter if starter in s.alive else s.nxt(starter)
        s.played, s.last = [], None

    def play(s, seat, card):
        if seat != s.cur or card not in s.hands[seat] or len(s.played) >= 3:
            return False
        s.hands[seat].remove(card)
        s.played.append(card)
        return True

    def end(s, seat):
        """Tashlovni yakunlaydi. Qaytaradi: tashlangan karta soni yoki None."""
        if seat != s.cur or not s.played: return None
        n = len(s.played)
        s.last = (seat, s.played)
        s.played = []
        s.cur = s.nxt(seat)
        return n

    def trust(s, seat):
        """Ishondim: tashlovni qabul qiladi, navbat shu o'yinchiga o'tadi va u tashlaydi."""
        if seat != s.cur or s.played or not s.last or not s.hands[seat]: return False
        s.last = None
        return True

    def challenge(s, seat):
        """Yolg'onchi deydi. Qaytaradi: (kartalar, rost_mi, yolg'onchi, yutqazgan) yoki None."""
        if seat != s.cur or s.played or not s.last: return None
        liar, cards = s.last
        truthful = all(c in (s.table, "J") for c in cards)
        loser = seat if truthful else liar
        s.last = None
        return cards, truthful, liar, loser

    def spin(s, seat):
        p = 1 / (6 - s.spins[seat])
        s.spins[seat] += 1
        dead = random.random() < p
        if dead and seat in s.alive: s.alive.remove(seat)
        return dead, p
