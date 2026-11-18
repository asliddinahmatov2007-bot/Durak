import io
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

W, H = 320, 448
SYM = "♠♥♦♣"
LET = "SHDC"
RED, BLACK = (205, 32, 48), (25, 25, 28)

def suit(d, cx, cy, s, kind, col):
    if kind == "♦":
        d.polygon([(cx, cy - s), (cx + .68 * s, cy), (cx, cy + s), (cx - .68 * s, cy)], fill=col)
    elif kind == "♥":
        r = .54 * s
        for dx in (-.5, .5): d.ellipse([cx + dx * s - r, cy - .35 * s - r, cx + dx * s + r, cy - .35 * s + r], fill=col)
        d.polygon([(cx - 1.02 * s, cy - .1 * s), (cx + 1.02 * s, cy - .1 * s), (cx, cy + s)], fill=col)
    elif kind == "♠":
        r = .54 * s
        for dx in (-.5, .5): d.ellipse([cx + dx * s - r, cy + .2 * s - r, cx + dx * s + r, cy + .2 * s + r], fill=col)
        d.polygon([(cx - 1.02 * s, cy + .0 * s), (cx + 1.02 * s, cy + .0 * s), (cx, cy - s)], fill=col)
        d.polygon([(cx, cy + .1 * s), (cx - .3 * s, cy + s), (cx + .3 * s, cy + s)], fill=col)
    else:
        r = .46 * s
        for x, y in ((0, -.5), (-.58, .22), (.58, .22)):
            d.ellipse([cx + x * s - r, cy + y * s - r, cx + x * s + r, cy + y * s + r], fill=col)
        d.polygon([(cx, cy), (cx - .3 * s, cy + s), (cx + .3 * s, cy + s)], fill=col)

L, M, Rr = 120, 160, 200
PIPS = {
    "6": [(L, 140), (Rr, 140), (L, 224), (Rr, 224), (L, 308), (Rr, 308)],
    "7": [(L, 140), (Rr, 140), (L, 224), (Rr, 224), (L, 308), (Rr, 308), (M, 182)],
    "8": [(L, 140), (Rr, 140), (L, 224), (Rr, 224), (L, 308), (Rr, 308), (M, 182), (M, 266)],
    "9": [(L, 130), (Rr, 130), (L, 193), (Rr, 193), (L, 255), (Rr, 255), (L, 318), (Rr, 318), (M, 224)],
    "10": [(L, 130), (Rr, 130), (L, 193), (Rr, 193), (L, 255), (Rr, 255), (L, 318), (Rr, 318), (M, 161), (M, 287)],
}

@lru_cache(maxsize=64)
def card_jpg(code):
    rank, sy = code[:-1], code[-1]
    col = RED if sy in "♥♦" else BLACK
    img = Image.new("RGB", (W, H), (47, 107, 63))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, W - 8, H - 8], radius=26, fill=(250, 250, 250), outline=(190, 190, 190), width=2)
    corner = Image.new("RGBA", (84, 150), (0, 0, 0, 0))
    cd = ImageDraw.Draw(corner)
    cd.text((42, 34), rank, font=ImageFont.load_default(size=52 if len(rank) < 2 else 44), fill=col, anchor="mm")
    suit(cd, 42, 100, 20, sy, col)
    img.paste(corner, (12, 14), corner)
    r2 = corner.rotate(180)
    img.paste(r2, (W - 12 - 84, H - 14 - 150), r2)
    if rank in PIPS:
        for x, y in PIPS[rank]: suit(d, x, y, 24, sy, col)
    elif rank == "A":
        suit(d, W // 2, H // 2, 78, sy, col)
    else:
        d.text((W // 2, H // 2 - 28), rank, font=ImageFont.load_default(size=170), fill=col, anchor="mm")
        suit(d, W // 2, H // 2 + 96, 38, sy, col)
    out = io.BytesIO(); img.save(out, "JPEG", quality=88)
    return out.getvalue()

def by_name(n):  # "10H" -> jpg
    rank, let = n[:-1], n[-1]
    if let not in LET or rank not in ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]: raise ValueError
    return card_jpg(rank + SYM[LET.index(let)])

def url_name(c): return c[:-1] + LET[SYM.index(c[-1])]
