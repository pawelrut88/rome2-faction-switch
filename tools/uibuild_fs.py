"""Build the faction-switch UI: the vanilla campaign_tactical_map layout plus a "Switch faction" button and a faction
list window (moved under menu_bar by Lua at runtime).

usage: python tools/uibuild_fs.py   (from the project folder; reads ui_src/, writes build/campaign_tactical_map_fs.xml and
       build/fs_factions.lua)

Rome II's Lua can't create UI components (no CreateComponent), so everything is pre-built here (etwng ui2xml text,
turned into the binary layout by xml2ui in tools/build_pack.sh). Sources, all the game's own files:
  ui_src/campaign_tactical_map.xml <- data_rome2.pack ui/campaign ui/campaign_tactical_map (replaced by our pack)
  ui_src/menu_bar.xml        <- data_rome2.pack ui/common ui/menu_bar        (only copied from: button_menu)
  ui_src/load-save_game.xml  <- data_rome2.pack ui/campaign ui/load-save_game (only copied from)
The button is a copy of button_menu with icon_swap.png. The window is a copy of the Load Game panel with its title,
list (one row per faction, rows pre-built) and OK/cancel; the save-specific parts are dropped and the engine
controllers that would fill it with saves (IngameSaveLoad, SPCampaignSaveInfo) are removed.
Helper functions follow population-supply tools/uibuild.py.
"""
import re, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # uitree.py: copy of population-supply tools/uitree.py (2026-11-23)
from uitree import parse

def load(p):
    t = open(os.path.join(HERE, p), encoding='utf-8-sig').read()
    return t, t.split('\n')

mb_text, mb = load('ui_src/menu_bar.xml')
ls_text, ls = load('ui_src/load-save_game.xml')
ct_text, ct = load('ui_src/campaign_tactical_map.xml')
mb_tree, ls_tree, ct_tree = parse(mb), parse(ls), parse(ct)

def find(tree, name, parent=None):
    def rec(n):
        for c in n.children:
            if c.name == name and (parent is None or (c.parent and c.parent.name == parent)): return c
            r = rec(c)
            if r: return r
    return rec(tree)

used = set(int(x) for x in re.findall(r'<u>(\d+)</u><!-- ID', mb_text + ls_text + ct_text))
next_id = [max(used) + 1000]
assert next_id[0] + 32 * 20000 < 2 ** 31, max(used)

def block(lines, node): return lines[node.start:node.end + 1]
def dedent(bl):
    ind = len(bl[0]) - len(bl[0].lstrip())
    return [l[ind:] if l[:ind].strip() == '' else l.lstrip() for l in bl]
def indent(bl, n): return [(' ' * n + l) if l else l for l in bl]

def top_only(bl, fn):
    out, depth = [], 0
    for l in bl:
        s = l.strip()
        if s == '<uientry>': depth += 1
        out.append(fn(l) if depth == 1 else l)
        if s == '</uientry>': depth -= 1
    return out

def remap_ids(bl):
    ids = set(int(x) for x in re.findall(r'<u>(\d+)</u><!-- ID', '\n'.join(bl)))
    m = {}
    for old in sorted(ids):
        next_id[0] += 32; m[old] = next_id[0]
    def sub(mo):
        v = int(mo.group(2)); return mo.group(1) + str(m.get(v, v)) + mo.group(3)
    return [re.sub(r'(<[ui]>)(\d+)(</[ui]>)', sub, l) for l in bl]

def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def set_top(bl, name=None, x=None, y=None, tooltip=None, dock=None, controller=None):
    done = set()
    def fn(l):
        s = l.strip()
        if name is not None and 'n' not in done and s.endswith('<!-- title -->'):
            done.add('n'); return re.sub(r'<s>.*</s>', '<s>%s</s>' % name, l)
        if controller is not None and 'c' not in done and s.endswith('<!-- title2 -->'):
            done.add('c'); return re.sub(r'<s>.*</s>', '<s>%s</s>' % controller, l)
        if x is not None and 'x' not in done and s.endswith('<!-- x offset -->'):
            done.add('x'); return re.sub(r'<i>-?\d+</i>', '<i>%d</i>' % x, l)
        if y is not None and 'y' not in done and s.endswith('<!-- y offset -->'):
            done.add('y'); return re.sub(r'<i>-?\d+</i>', '<i>%d</i>' % y, l)
        if tooltip is not None and 't' not in done and s.endswith('<!-- tooltip text -->'):
            done.add('t'); return re.sub(r'<unicode>.*</unicode>', '<unicode>%s</unicode>' % esc(tooltip), l)
        if tooltip is not None and 'ti' not in done and s.endswith('<!-- tooltip id -->'):
            done.add('ti'); return re.sub(r'<unicode>.*</unicode>', '<unicode></unicode>', l)
        if dock is not None:
            for k, tag in (('d', '<!-- docking? -->'), ('dx', '<!-- docking x? -->'), ('dy', '<!-- docking y? -->')):
                if k not in done and tag in s:
                    done.add(k); return re.sub(r'<i>-?\d+</i>', '<i>%d</i>' % (dock if k == 'd' else 0), l, count=1)
        return l
    return top_only(bl, fn)

def set_text(bl, txt):
    """State text of every state of the top entry; clears the localisation id so the game shows our text."""
    def fn(l):
        s = l.strip()
        if s.endswith('<!-- state text -->'): return re.sub(r'<unicode>.*</unicode>', '<unicode>%s</unicode>' % esc(txt), l)
        if s.endswith('<!-- localization id -->'): return re.sub(r'<unicode>.*</unicode>', '<unicode></unicode>', l)
        return l
    return top_only(bl, fn)

def set_size(bl, w, h):
    """Every state size and image_use size of the top entry -> w x h."""
    st = {'state': False, 'use': False, 'xs': False}
    def fn(l):
        s = l.strip()
        if s == '<state>': st['state'] = True
        elif s == '</state>': st['state'] = False
        elif s == '<image_use>': st['use'] = True
        elif s == '</image_use>': st['use'] = False
        if (st['state'] or st['use']) and s.endswith('<!-- x size -->'):
            return re.sub(r'<([ui])>\d+</[ui]>', lambda m: '<%s>%d</%s>' % (m.group(1), w, m.group(1)), l)
        if (st['state'] or st['use']) and s.endswith('<!-- y size -->'):
            return re.sub(r'<([ui])>\d+</[ui]>', lambda m: '<%s>%d</%s>' % (m.group(1), h, m.group(1)), l)
        return l
    return top_only(bl, fn)

def children_of(bl):
    """(head lines up to and including '<children count=..>', [child blocks], tail lines) of the top entry."""
    depth, i = 0, 0
    while True:
        s = bl[i].strip()
        if s == '<uientry>': depth += 1
        if s == '</uientry>': depth -= 1
        if depth == 1 and s.startswith('<children count='): break
        i += 1
    head = bl[:i + 1]; kids = []; j = i + 1; ind = len(bl[i]) - len(bl[i].lstrip())
    while bl[j].strip() != '</children>' or len(bl[j]) - len(bl[j].lstrip()) != ind:
        assert bl[j].strip() == '<uientry>', bl[j]
        d, k = 0, j
        while True:
            t = bl[k].strip()
            if t == '<uientry>': d += 1
            if t == '</uientry>': d -= 1
            if d == 0: break
            k += 1
        kids.append(dedent(bl[j:k + 1])); j = k + 1
    return head, kids, bl[j:]

def with_children(bl, kids):
    head, _, tail = children_of(bl)
    ind = len(head[-1]) - len(head[-1].lstrip())
    head = head[:-1] + [' ' * ind + '<children count="%d">' % len(kids)]
    out = list(head)
    for k in kids: out.extend(indent(k, ind + 2))
    return out + tail

def name_of(bl):
    for l in bl:
        m = re.match(r'\s*<s>(.*)</s><!-- title -->', l)
        if m: return m.group(1)

def child(bl, name):
    return [k for k in children_of(bl)[1] if name_of(k) == name][0]

def replace_child(bl, name, new):
    _, kids, _ = children_of(bl)
    return with_children(bl, [new if name_of(k) == name else k for k in kids])

# ---------- faction list
# variant: '' = vanilla; 'dei' = DeI's playable factions of main_rome (its start file) with DeI's names
# (work/dei/factions_dei.loc.tsv, from DeI release 12 Part1 text/db/__Factions_DeI.loc); output in build/dei/
VARIANT = sys.argv[1] if len(sys.argv) > 1 else ''
OUTDIR = os.path.join(HERE, 'build', VARIANT) if VARIANT else os.path.join(HERE, 'build')
names = {}
for t in ['work/vanilla/text/db/factions.loc.tsv'] + (['work/dei/factions_dei.loc.tsv'] if VARIANT == 'dei' else []):
    for l in open(os.path.join(HERE, t), encoding='utf-8'):
        p = l.rstrip('\n').split('\t')
        if len(p) >= 2: names[p[0]] = p[1]
keys = open(os.path.join(HERE, 'build/playable_%smain_rome.txt' % (VARIANT + '_' if VARIANT else ''))).read().split()
facs = [(k, names['factions_screen_name_' + k]) for k in keys]
facs.sort(key=lambda kv: kv[1])

# ---------- the button: copy of button_menu, right of the advice button (where the Twitch button sits; hidden in SP)
btn = dedent(block(mb, find(mb_tree, 'button_menu')))
btn = remap_ids(btn)
btn = set_top(btn, name='fs_switch_button', x=172, y=0, tooltip='Switch faction||Choose another faction to play.')
btn = [l.replace('ui\\skins\\default\\icon_menu.png', 'ui\\skins\\default\\icon_swap.png') for l in btn]
assert any('icon_swap.png' in l for l in btn)

# ---------- the window: copy of the Load Game panel
W, H = 560, 470
win = dedent(block(ls, find(ls_tree, 'load-save_game')))
win = remap_ids(win)
_, kids, _ = children_of(win)
keep = {'panel_decoration', 'bg_title_frame', 'listview', 'button_ok', 'button_cancel'}
kids = [k for k in kids if name_of(k) in keep]
out = []
for k in kids:
    n = name_of(k)
    if n == 'panel_decoration': k = set_top(k, x=(W - 156) // 2)
    elif n == 'bg_title_frame':
        k = set_size(k, W, 36)
        tx = child(k, 'TX_save_game')
        tx = set_size(set_text(set_top(tx, name='fs_title'), 'Switch faction'), W, 36)
        hl = set_size(set_top(child(tx, 'h_line'), x=18), W - 36, 24)
        tx = with_children(tx, [hl]); k = with_children(k, [tx])
    elif n == 'listview':
        k = set_top(k, x=(W - 500) // 2 - 7, y=60)
        lc = child(k, 'list_clip'); lb = child(lc, 'list_box'); row = child(lb, 'row_example')
        rows = []
        # first row 'fs_row_msg' / 'fs_label_msg': not a faction; Lua shows it alone for wait and error texts
        for i, (key, label) in enumerate([('msg', '')] + facs):
            r = set_top(row, name='fs_row_' + key, controller='')
            _, rk, _ = children_of(r)
            # unique name: Find is not reliably scoped to the row; text baked in the layout shows 'dy', Lua sets it
            nm = set_text(set_top([l for l in rk if name_of(l) == 'name'][0], name='fs_label_' + key), label)
            nm = set_size(nm, 498, 24)
            r = with_children(r, [nm])
            rows.append(remap_ids(r))
        lb = with_children(lb, rows); lc = with_children(lc, [lb])
        hd = child(k, 'headers')
        hn = child(hd, 'name'); htx = set_text(child(hn, 'head_tx'), 'Faction')
        hn = with_children(set_size(hn, 498, 28), [set_size(htx, 498, 30)])
        hd = with_children(hd, [hn])
        k = replace_child(replace_child(k, 'list_clip', lc), 'headers', hd)
    elif n == 'button_ok': k = set_top(k, name='fs_button_ok', x=W // 2 - 60, y=H - 66, tooltip='Switch to the chosen faction')
    elif n == 'button_cancel': k = set_top(k, name='fs_button_cancel', x=W // 2 + 10, y=H - 66, tooltip='Close')
    out.append(k)
win = with_children(win, out)
win = set_size(set_top(win, name='fs_switch_panel', x=360, y=150, dock=0, controller=''), W, H)

# ---------- put both into the HOST layout, campaign_tactical_map (not menu_bar: Consul Scriptum replaces menu_bar;
# neither Consul nor DeI replaces campaign_tactical_map). fs_switch.lua moves both under menu_bar with Adopt at
# UICreated (menu_bar never closes; an adopted component dies with its new parent's panel, SHARED_KNOWLEDGE).
host = dedent(block(ct, find(ct_tree, 'campaign_tactical_map')))
_, hkids, _ = children_of(host)
host = with_children(host, hkids + [btn, win])
hn = find(ct_tree, 'campaign_tactical_map')
ind = len(ct[hn.start]) - len(ct[hn.start].lstrip())
new = ct[:hn.start] + indent(host, ind) + ct[hn.end + 1:]
os.makedirs(OUTDIR, exist_ok=True)
open(os.path.join(OUTDIR, 'campaign_tactical_map_fs.xml'), 'w', encoding='utf-8').write('\n'.join(new))

# ---------- the Lua table of the list (order = rows)
with open(os.path.join(OUTDIR, 'fs_factions.lua'), 'w', encoding='utf-8') as f:
    f.write('-- generated by tools/uibuild_fs.py: the faction list rows (key, English name), sorted by name\n')
    f.write('return {\n' + ''.join('  { "%s", "%s" },\n' % kv for kv in facs) + '}\n')
assert next_id[0] < 2 ** 31
print('rows %d, window %dx%d, ids up to %d' % (len(facs), W, H, next_id[0]))
