# Helpers for Rome II save files (faction-switch project).
# Reuses the IA session's ESF code READ-ONLY from F:\ROME2\Claude 01\handoff (esf.py, startpos_tool.py, lzwin.py,
# addfac.py); nothing there is changed. A save = outer ESF (SAVE_GAME_HEADER + COMPRESSED_DATA); COMPRESSED_DATA
# holds an LZMA stream of the inner ESF (CAMPAIGN_SAVE_GAME: BUILD, SAVE_GAME_HEADER, CAMPAIGN_ENV).
import sys, os, struct
IA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor_ia')   # copy of F:\ROME2\Claude 01\handoff
if IA not in sys.path: sys.path.insert(0, IA)
import esf, startpos_tool                      # noqa: E402
from esf import Rec, Val, Arr                  # noqa: E402,F401
from addfac import Doc                         # noqa: E402,F401  (string tables: Doc.asc / i2a)

def kids(n): return [x for el in n.kids for x in el] if n.block else n.kids

def sval(D, v): return D.i2a.get(struct.unpack('<I', v.raw)[0])        # ascii string value (type 0x0f)

def child(D, n, name):
    r = [k for k in n.kids if isinstance(k, Rec) and D.N[k.name] == name]
    assert len(r) == 1, (name, len(r)); return r[0]

def find(D, n, name, out=None, depth=0, maxd=8):
    out = [] if out is None else out
    if isinstance(n, Rec):
        if D.N[n.name] == name: out.append(n)
        if depth < maxd:
            for k in kids(n): find(D, k, name, out, depth + 1, maxd)
    return out

def env(D): return child(D, D.d['root'], 'CAMPAIGN_ENV')

def factions(D):
    """{faction_key: FACTION record} in FACTION_ARRAY order (index 0 = first in turn order)."""
    fa = find(D, env(D), 'FACTION_ARRAY', maxd=4)        # CAMPAIGN_ENV/CAMPAIGN_MODEL/WORLD/FACTION_ARRAY
    assert len(fa) == 1
    out = {}
    for el in fa[0].kids:
        f = el[0]; k = [x for x in f.kids if isinstance(x, Val) and x.t == 0x0f][0]
        out[sval(D, k)] = f
    return out

def unpack(save, inner): startpos_tool.unpack(save, inner)
def pack(save, inner, dst): startpos_tool.pack(save, inner, dst)   # recompresses with lzwin (liblzma 5.8.1)

# ---------- structural diff ----------
def _res(D, x):
    if x.t == 0x0f: return 'A:' + repr(sval(D, x))
    if x.t == 0x0e: return 'U#%d' % struct.unpack('<I', x.raw)[0]
    return '%02x:%s' % (x.t, x.raw.hex())

def diff(A, a, B, b, path='', out=None, lim=100000):
    out = [] if out is None else out
    if len(out) > lim: return out
    if type(a) != type(b): out.append((path, 'type')); return out
    if isinstance(a, Rec):
        p = path + '/' + A.N[a.name]
        if A.N[a.name] != B.N[b.name]: out.append((p, 'name ' + B.N[b.name])); return out
        if a.block:
            if len(a.kids) != len(b.kids): out.append((p, 'count %d/%d' % (len(a.kids), len(b.kids)))); return out
            for i, (x, y) in enumerate(zip(a.kids, b.kids)):
                if len(x) != len(y): out.append((p + '[%d]' % i, 'elemlen')); continue
                for j, (u, v) in enumerate(zip(x, y)): diff(A, u, B, v, p + '[%d].%d' % (i, j), out, lim)
        else:
            if len(a.kids) != len(b.kids): out.append((p, 'kids %d/%d' % (len(a.kids), len(b.kids)))); return out
            for j, (u, v) in enumerate(zip(a.kids, b.kids)): diff(A, u, B, v, p + '.%d' % j, out, lim)
    elif isinstance(a, Arr):
        if a.t == 0x4f:
            sa = [A.i2a.get(struct.unpack_from('<I', a.raw, i)[0]) for i in range(0, len(a.raw), 4)]
            sb = [B.i2a.get(struct.unpack_from('<I', b.raw, i)[0]) for i in range(0, len(b.raw), 4)]
            if sa != sb: out.append((path, 'strarr %s / %s' % (sa[:6], sb[:6])))
        elif a.raw != b.raw: out.append((path, 'arr%02x len %d/%d' % (a.t, len(a.raw), len(b.raw))))
    else:
        ra, rb = _res(A, a), _res(B, b)
        if ra != rb: out.append((path, '%s -> %s' % (ra, rb)))
    return out
