"""Steam logo (2026-11-23): the user's ChatGPT artwork (steam_logo/faction_switch_original.png, two shields + arrows)
with the game's own Rome and Carthage emblems (ui/flags/rome|carthage/mon_256.png from data.pack, in
steam_logo/game_flags) set into the shields, and the title in the style of the user's other mod images (small top
word between gold lines, big gold Trajan title, small subtitle). Writes steam_logo/faction_switch.png (512x512) and
steam_logo/faction_switch_1024.png.  usage: python tools/make_logo.py [dei]
'dei': DeI's own Rome emblem (DeI Part2 ui/flags/rome; Carthage is vanilla's), steam_logo/game_flags_dei,
top word 'DeI', subtitle 'SUBMOD . GRAND CAMPAIGN', output steam_logo/faction_switch_dei(_1024).png."""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = lambda *p: os.path.join(HERE, 'steam_logo', *p)
FONT = r'C:\Windows\Fonts\TrajanPro-Bold.otf'
DEI = sys.argv[1:2] == ['dei']
FLAGS, TOP, SUB, NAME = (('game_flags_dei', 'DeI', ('SUBMOD', 'GRAND CAMPAIGN'), 'old/faction_switch_dei_composite') if DEI else
                         ('game_flags', 'ROME II', ('GRAND CAMPAIGN', 'VANILLA'), 'old/faction_switch_composite'))
S = 1254                                  # work size = the artwork's size

art = Image.open(L('faction_switch_original.png')).convert('RGBA')
# shield centres and the radius of the emblem set into each (measured on the 1254 artwork; inside the bronze rims,
# clear of the arrow heads and of the left shield's rim over the right one)
SHIELDS = [((360, 605), 'rome_mon_256.png'), ((897, 610), 'carthage_mon_256.png')]
R = 244
RING = 20     # opaque dark-bronze frame around each emblem: covers what is left of the old symbols
for (cx, cy), f in SHIELDS:
    fl = Image.open(L(FLAGS, f)).convert('RGBA').resize((2 * R, 2 * R), Image.LANCZOS)
    m = Image.new('L', (2 * R, 2 * R), 0); ImageDraw.Draw(m).ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=255)
    m = Image.composite(fl.getchannel('A'), Image.new('L', m.size, 0), m)
    # thin dark ring under the emblem so it sits in the shield
    D2 = 2 * (R + RING)
    sh = Image.new('RGBA', (D2 + 20, D2 + 20), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((10, 10, D2 + 9, D2 + 9), fill=(0, 0, 0, 150))
    art.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), (cx - R - RING - 10, cy - R - RING - 6))
    fr = Image.new('RGBA', (D2, D2), (0, 0, 0, 0)); df = ImageDraw.Draw(fr)
    df.ellipse((0, 0, D2 - 1, D2 - 1), fill=(92, 58, 26, 255))
    df.ellipse((4, 4, D2 - 5, D2 - 5), fill=(150, 104, 44, 255))
    df.ellipse((9, 9, D2 - 10, D2 - 10), fill=(70, 44, 20, 255))
    art.alpha_composite(fr, (cx - R - RING, cy - R - RING))
    art.paste(fl, (cx - R, cy - R), m)

# canvas: the artwork scaled down at the top, dark below for the text
canvas = art.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.55))
canvas = Image.blend(canvas, Image.new('RGBA', (S, S), (18, 15, 13, 255)), 0.8)
k = 0.74; aw = int(S * k)
small = art.resize((aw, aw), Image.LANCZOS)
fm = Image.new('L', (aw, aw), 0); ImageDraw.Draw(fm).rectangle((60, 0, aw - 61, aw - 60), fill=255)
small.putalpha(fm.filter(ImageFilter.GaussianBlur(40)))
canvas.alpha_composite(small, ((S - aw) // 2, 0))
# fade the artwork's lower edge into the dark
fade = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(fade)
for y in range(int(aw * 0.80), S):
    a = min(255, int(255 * (y - aw * 0.80) / (aw * 0.22)))
    d.line([(0, y), (S, y)], fill=(12, 10, 9, a))
canvas.alpha_composite(fade)

def gold_text(img, text, size, cy, track=0):
    f = ImageFont.truetype(FONT, size)
    w = sum(f.getlength(c) for c in text) + track * (len(text) - 1)
    x0 = (S - w) / 2; top = cy - size // 2
    mask = Image.new('L', (S, S), 0); dm = ImageDraw.Draw(mask); x = x0
    for c in text: dm.text((x, top), c, font=f, fill=255); x += f.getlength(c) + track
    bb = mask.getbbox()
    # shadow, dark edge, gold vertical gradient
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0)); sh.putalpha(mask.filter(ImageFilter.GaussianBlur(size / 14)).point(lambda v: int(v * 0.9)))
    img.alpha_composite(sh, (0, size // 20))
    edge = Image.new('RGBA', (S, S), (60, 35, 10, 255)); edge.putalpha(mask.filter(ImageFilter.MaxFilter(3)))
    img.alpha_composite(edge)
    grad = Image.new('RGBA', (S, S)); g = ImageDraw.Draw(grad)
    for y in range(bb[1], bb[3] + 1):
        t = (y - bb[1]) / max(1, bb[3] - bb[1])
        stops = [(0, (255, 238, 170)), (0.45, (232, 186, 88)), (0.55, (196, 140, 52)), (1, (240, 200, 110))]
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0); col = tuple(int(c0[i] + (c1[i] - c0[i]) * u) for i in range(3)); break
        g.line([(0, y), (S, y)], fill=col + (255,))
    grad.putalpha(mask); img.alpha_composite(grad)
    return bb

d = ImageDraw.Draw(canvas)
bb = gold_text(canvas, TOP, 62, 935, track=4)
# thin gold lines both sides of the top word
for x0, x1 in ((150, bb[0] - 30), (bb[2] + 30, S - 150)):
    d.line([(x0, 937), (x1, 937)], fill=(214, 168, 80, 255), width=3)
gold_text(canvas, 'FACTION SWITCH', 118, 1050, track=2)
# subtitle: two words with a drawn dot between (Trajan has no bullet glyph)
sub = ImageFont.truetype(FONT, 44); tr = 6
wa = sum(sub.getlength(c) for c in SUB[0]) + tr * (len(SUB[0]) - 1); wb = sum(sub.getlength(c) for c in SUB[1]) + tr * (len(SUB[1]) - 1)
gap = 60; x0 = (S - (wa + gap + wb)) / 2
def word(text, x):
    m = Image.new('RGBA', (S, S), (0, 0, 0, 0)); gold_text(m, text, 44, 1160, track=tr)
    bbm = m.getbbox(); canvas.alpha_composite(m.crop(bbm), (int(x), bbm[1]))
word(SUB[0], x0); word(SUB[1], x0 + wa + gap)
dx, dy = x0 + wa + gap / 2, 1158
d.ellipse((dx - 7, dy - 7, dx + 7, dy + 7), fill=(226, 180, 90, 255))

out = canvas.convert('RGB')
out.resize((1024, 1024), Image.LANCZOS).save(L(NAME + '_1024.png'), optimize=True)
out.resize((512, 512), Image.LANCZOS).save(L(NAME + '.png'), optimize=True)
print('wrote', L(NAME + '.png'), os.path.getsize(L(NAME + '.png')), 'bytes')
