"""Rome II CAMPAIGN_SHROUD bit arrays (faction-switch, 2026-11-23; format worked out from vanilla saves).

A faction's CAMPAIGN_SHROUD holds three QUAD_TREE_BIT_ARRAY records: width 1357, height 1110, size 2048, then a
quadtree (type 0x46 blob). Array 0 and 1 are the explored and the visible area (2 is empty in the saves seen).
Quadtree, depth first from a 2048 root: a node is one header byte; header 0x00 = leaf, followed by 8 bytes = 8x8
bits (row by row, high bit first), each bit covering (node size / 8) cells; any other header holds 4 two-bit child
codes, low bits first, children in order (0,0) (1,0) (0,1) (1,1): 1 = a child node follows, 2 = all clear,
3 = all set. The game's encoder subdivides down to size 8 and writes an all-clear root as one leaf; encode() does
the same (decode + encode gives the game's bytes back for all 15 arrays of a 5-human save).
Cells: column = 2 * display x, row = 2048 - 2 * display y (checked on the LINE_OF_SIGHT boxes in the save)."""

# Pure Python (the helper exe has no numpy). A node is E (all clear), F (all set), ('L', rows) = a leaf of 8x8 bits
# over the node's square, or ('N', [4 children]).
E, F = 'E', 'F'
ORDER = [(0, 0), (1, 0), (0, 1), (1, 1)]

def parse(d):
    pos = [0]
    def node():
        h = d[pos[0]]; pos[0] += 1
        if h == 0:
            rows = tuple(d[pos[0]:pos[0] + 8]); pos[0] += 8; return ('L', rows)
        kids = []
        for i in range(4):
            c = (h >> (2 * i)) & 3
            if c == 1: kids.append(node())
            elif c == 2: kids.append(E)
            elif c == 3: kids.append(F)
            else: raise ValueError('quadtree child code 0 not understood')
        return ('N', kids)
    t = node()
    if pos[0] != len(d): raise ValueError('quadtree: %d of %d bytes used' % (pos[0], len(d)))
    return t

def _split_leaf(rows):
    """a leaf over a square of size s -> 4 leaves over the quarters (each bit of the quarter doubled)"""
    out = []
    for dx, dy in ORDER:
        sub = []
        for r in range(8):
            src = rows[dy * 4 + r // 2]; v = 0
            for b in range(8):
                if src >> (7 - (dx * 4 + b // 2)) & 1: v |= 1 << (7 - b)
            sub.append(v)
        out.append(('L', tuple(sub)))
    return out

def _canon(n, s):
    """the game's form: leaves only at size 8, uniform squares as E/F"""
    if n in (E, F): return n
    if n[0] == 'L':
        if all(r == 0 for r in n[1]): return E
        if all(r == 0xff for r in n[1]): return F
        if s == 8: return n
        return _canon(('N', _split_leaf(n[1])), s)
    kids = [_canon(k, s // 2) for k in n[1]]
    if all(k == E for k in kids): return E
    if all(k == F for k in kids): return F
    return ('N', kids)

def encode_tree(t, size=2048):
    t = _canon(t, size); out = bytearray()
    def node(n):
        if n[0] == 'L': out.append(0); out.extend(n[1]); return
        h = 0
        for i, k in enumerate(n[1]): h |= (2 if k == E else 3 if k == F else 1) << (2 * i)
        out.append(h)
        for k in n[1]:
            if k not in (E, F): node(k)
    if t == E: out.extend(bytes(9))
    elif t == F: out.extend(bytes([0]) + bytes([0xff]) * 8)   # not seen in saves
    else: node(t)
    return bytes(out)

def count(t, s=2048):
    if t == E: return 0
    if t == F: return s * s
    if t[0] == 'L': c = (s // 8) ** 2; return c * sum(bin(r).count('1') for r in t[1])
    return sum(count(k, s // 2) for k in t[1])

def paint_circle(t, x, y, s, cx, cy, r2):
    """set every cell (column i, row j) with (i-cx)^2 + (j-cy)^2 <= r2 inside the square (x, y, s)"""
    if t == F: return F
    nx = min(max(cx, x), x + s - 1); ny = min(max(cy, y), y + s - 1)
    if (nx - cx) ** 2 + (ny - cy) ** 2 > r2: return t                       # no cell of the square in the circle
    fx = max(abs(x - cx), abs(x + s - 1 - cx)); fy = max(abs(y - cy), abs(y + s - 1 - cy))
    if fx * fx + fy * fy <= r2: return F                                      # whole square in the circle
    if s == 8:
        rows = list(t[1]) if t != E else [0] * 8
        for j in range(8):
            for i in range(8):
                if (x + i - cx) ** 2 + (y + j - cy) ** 2 <= r2: rows[j] |= 1 << (7 - i)
        return ('L', tuple(rows))
    if t == E: kids = [E] * 4
    elif t[0] == 'L': kids = _split_leaf(t[1])
    else: kids = list(t[1])
    h = s // 2
    return ('N', [paint_circle(k, x + dx * h, y + dy * h, h, cx, cy, r2) for k, (dx, dy) in zip(kids, ORDER)])

def reveal(blob, points, radius, size=2048, w=1357, h=1110):
    """Set every cell within `radius` (display units) of each (x, y) display position. Returns (new blob, cells)."""
    t = parse(blob); before = count(t); r = 2 * radius
    for x, y in points:
        cx, cy = round(2 * x), round(size - 2 * y)
        if not (0 <= cx < w and size - h <= cy < size): continue   # off the map: skip
        t = paint_circle(t, 0, 0, size, cx, cy, r * r)
    return encode_tree(t, size), count(t) - before
