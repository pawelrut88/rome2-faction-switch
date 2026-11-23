"""Steam logo text (2026-11-23): the user's textless ChatGPT artwork (steam_logo/faction_switch_notext.png and
faction_switch_dei_notext.png, 1254x1254) plus the title in the size and layout of the user's DeI Imperator Augustus
logos (data/@@@@@PAW_Imperator_Augustus.png, measured at 512: top word cap ~34 px from y 339, title lines cap ~33 px,
~316 px wide, gold line at y 462, subtitle cap ~11 px). Soft black band behind the text so it can sit over the art.
usage: python tools/make_logo_text.py [dei]   writes steam_logo/faction_switch(_dei).png (512) and _1024.png"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = lambda *p: os.path.join(HERE, 'steam_logo', *p)
FONT = r'C:\Windows\Fonts\TrajanPro-Bold.otf'
DEI = sys.argv[1:2] == ['dei']
SRC, TOP, SUB, OUT = (('faction_switch_dei_notext.png', 'DeI', ('SUBMOD', 'GRAND CAMPAIGN'), 'faction_switch_dei') if DEI
                      else ('faction_switch_notext.png', 'ROME II', ('GRAND CAMPAIGN', 'VANILLA'), 'faction_switch'))
S = 1254
K = S / 512                                # reference measured at 512

img = Image.open(L(SRC)).convert('RGBA')
assert img.size == (S, S)

def cap_size(cap_px):
    """font size whose capital H is cap_px tall"""
    f = ImageFont.truetype(FONT, 100); b = f.getbbox('H')
    return round(100 * cap_px / (b[3] - b[1]))

def text_mask(text, size, track):
    f = ImageFont.truetype(FONT, size)
    w = sum(f.getlength(c) for c in text) + track * (len(text) - 1)
    m = Image.new('L', (S, S), 0); d = ImageDraw.Draw(m); x = (S - w) / 2
    for c in text: d.text((x, 0), c, font=f, fill=255); x += f.getlength(c) + track
    return m

def place(mask, cap_top):
    """move the mask so the top of its letters is at cap_top"""
    bb = mask.getbbox(); out = Image.new('L', (S, S), 0)
    out.paste(mask.crop(bb), (bb[0], int(cap_top))); return out

STOPS = [(0, (255, 240, 178)), (0.42, (236, 192, 96)), (0.55, (190, 132, 46)), (1, (244, 206, 118))]
def gold(mask):
    bb = mask.getbbox()
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0)); sh.putalpha(mask.filter(ImageFilter.GaussianBlur(5)))
    img.alpha_composite(sh, (0, 4))
    edge = Image.new('RGBA', (S, S), (58, 34, 10, 255)); edge.putalpha(mask.filter(ImageFilter.MaxFilter(3)))
    img.alpha_composite(edge)
    grad = Image.new('RGBA', (S, S)); g = ImageDraw.Draw(grad)
    for y in range(bb[1], bb[3] + 1):
        t = (y - bb[1]) / max(1, bb[3] - bb[1])
        for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0); col = tuple(int(c0[i] + (c1[i] - c0[i]) * u) for i in range(3)); break
        g.line([(0, y), (S, y)], fill=col + (255,))
    grad.putalpha(mask); img.alpha_composite(grad)
    return bb

# layout (cap tops / heights from the reference, x K)
TOP_Y, TOP_CAP = 339 * K, 33 * K
T1_Y, T2_Y, T_CAP = 379 * K, 418 * K, 33 * K
LINE_Y = 462 * K
SUB_Y, SUB_CAP = 470 * K, 10.5 * K

# title on one line (user, 2026-11-23): as big as fits TITLE_W, bottom at the reference's title bottom
TITLE_W = 1000
tf = ImageFont.truetype(FONT, 100); tw = sum(tf.getlength(c) for c in 'FACTION SWITCH') + 4 * 13
T_CAP = min(T_CAP, 33 * K * TITLE_W / (tw * cap_size(33 * K) / 100))
T1_Y = 452 * K - T_CAP
TOP_Y = T1_Y - 14 * K - TOP_CAP
top = place(text_mask(TOP, cap_size(TOP_CAP), 6), TOP_Y)
t1 = place(text_mask('FACTION SWITCH', cap_size(T_CAP), 4), T1_Y)
t2 = Image.new('L', (S, S), 0)
fs = ImageFont.truetype(FONT, cap_size(SUB_CAP)); tr = 5
wa = sum(fs.getlength(c) for c in SUB[0]) + tr * (len(SUB[0]) - 1)
wb = sum(fs.getlength(c) for c in SUB[1]) + tr * (len(SUB[1]) - 1)
gap = 56; x0 = (S - (wa + gap + wb)) / 2
sub = Image.new('L', (S, S), 0)
for text, x in ((SUB[0], x0), (SUB[1], x0 + wa + gap)):
    m = place(text_mask(text, fs.size, tr), SUB_Y); bb = m.getbbox()
    sub.paste(m.crop(bb), (int(x), bb[1]), m.crop(bb))

# soft black band behind the text block (over the art's lower edge)
band = Image.new('L', (S, S), 0); bd = ImageDraw.Draw(band)
y0 = int(TOP_Y - 70)
for y in range(y0, S):
    bd.line([(0, y), (S, y)], fill=min(235, int(235 * (y - y0) / 110)))
blk = Image.new('RGBA', (S, S), (8, 6, 5, 255)); blk.putalpha(band.filter(ImageFilter.GaussianBlur(20)))
img.alpha_composite(blk)
text_all = Image.new('L', (S, S), 0)
for m in (top, t1, t2, sub): text_all.paste(255, (0, 0), m)
halo = Image.new('RGBA', (S, S), (0, 0, 0, 255)); halo.putalpha(text_all.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.8)))
img.alpha_composite(halo)

tb = gold(top); bb1 = gold(t1); bb2 = bb1; gold(sub)
d = ImageDraw.Draw(img); LC = (214, 168, 80, 255)
# thin gold lines beside the top word, and the line above the subtitle (as wide as the title)
tl, tr_ = min(bb1[0], bb2[0]), max(bb1[2], bb2[2])
ly = (tb[1] + tb[3]) // 2
ol, orr = tb[0] - 28 - 110, tb[2] + 28 + 110      # short lines, as in the earlier logo (user, 2026-11-23)
d.line([(ol, ly), (tb[0] - 28, ly)], fill=LC, width=3); d.line([(tb[2] + 28, ly), (orr, ly)], fill=LC, width=3)
d.line([(tl - 10, LINE_Y), (tr_ + 10, LINE_Y)], fill=LC, width=3)
dx, dy = x0 + wa + gap / 2, SUB_Y + SUB_CAP / 2
d.ellipse((dx - 6, dy - 6, dx + 6, dy + 6), fill=(226, 180, 90, 255))

out = img.convert('RGB')
out.resize((1024, 1024), Image.LANCZOS).save(L(OUT + '_1024.png'), optimize=True)
out.resize((512, 512), Image.LANCZOS).save(L(OUT + '.png'), optimize=True)
print('wrote', L(OUT + '.png'), os.path.getsize(L(OUT + '.png')), 'bytes; title width', tr_ - tl, 'px of', S)
