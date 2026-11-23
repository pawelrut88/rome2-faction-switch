#!/usr/bin/env python3
"""Rome 2 startpos.esf toolkit.

  python startpos_tool.py unpack  startpos.esf  inner.esf
  python startpos_tool.py pack    startpos.esf  inner.esf  new_startpos.esf
  python startpos_tool.py summary inner.esf

unpack : decompresses the campaign data hidden inside startpos.esf into a plain ESF.
pack   : takes the ORIGINAL startpos.esf (for its header/preopen data) plus an edited
         inner.esf, recompresses it, and writes a new startpos.esf.
summary: counts the main record types and lists faction keys.
"""
import sys, struct, lzma
import esf
from esf import Rec, Val, Arr

def _find(n, nm, names, out, depth=0, maxd=16):
    if isinstance(n, Rec):
        if names[n.name] == nm: out.append(n)
        if depth < maxd:
            kids = [k for el in n.kids for k in el] if n.block else n.kids
            for k in kids: _find(k, nm, names, out, depth+1, maxd)
    return out

def _cd(doc):
    N = doc['names']
    cd = [k for k in doc['root'].kids if isinstance(k, Rec) and N[k.name] == 'COMPRESSED_DATA'][0]
    return cd, cd.kids[0], cd.kids[1]          # record, LZMA array, info record

def _read_size(v):
    # uncompressed size can be stored as a plain u32 (0x08, little-endian) or the
    # 24-bit optimised form (0x18, which is big-endian)
    if v.t == 0x08: return struct.unpack('<I', v.raw)[0]
    if v.t == 0x18: return int.from_bytes(v.raw, 'big')
    if v.t == 0x17: return struct.unpack('<H', v.raw)[0]
    raise ValueError('unexpected size type 0x%02x' % v.t)

def _write_size(v, n):
    if v.t == 0x18 and n < (1 << 24): v.raw = n.to_bytes(3, 'big')
    else: v.t = 0x08; v.raw = struct.pack('<I', n)

def unpack(src, dst):
    doc = esf.load(src)
    cd, blob, info = _cd(doc)
    usz = _read_size(info.kids[0])
    props = info.kids[1].raw
    out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(props + struct.pack('<Q', usz) + blob.raw)
    assert len(out) == usz
    open(dst, 'wb').write(out)
    print('unpacked', usz, 'bytes ->', dst)

def pack(src, inner, dst):
    doc = esf.load(src)
    cd, blob, info = _cd(doc)
    data = open(inner, 'rb').read()
    esf.load(inner)                              # sanity: must parse
    pb = info.kids[1].raw                        # reuse the original file's LZMA settings
    q = pb[0]; lc = q % 9; q //= 9; lp = q % 5; pbits = q // 5
    dict_size = struct.unpack('<I', pb[1:5])[0]
    # The game's own files have NO end-of-stream marker. Python's lzma module cannot
    # omit it, so use the small helper built from lzenc.c (liblzma >= 5.4, LZMA1EXT).
    import os, subprocess, tempfile
    if os.name == 'nt':                          # Windows: same encoder via liblzma.dll (lzwin.py)
        import lzwin
        blob.raw = lzwin.compress(data, dict_size, lc, lp, pbits)
        _write_size(info.kids[0], len(data))
        esf.save(doc, dst)
        print('wrote', dst)
        return
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lzenc')
    if not os.path.exists(helper):
        raise SystemExit('lzenc helper not found. Build it with:  gcc -O2 -o lzenc lzenc.c /usr/lib/x86_64-linux-gnu/liblzma.so.5')
    with tempfile.TemporaryDirectory() as td:
        fin, fout = os.path.join(td, 'in'), os.path.join(td, 'out')
        open(fin, 'wb').write(data)
        subprocess.check_call([helper, fin, fout, str(dict_size), str(lc), str(lp), str(pbits)])
        comp = open(fout, 'rb').read()
    blob.raw = comp
    _write_size(info.kids[0], len(data))
    esf.save(doc, dst)
    print('wrote', dst)

def summary(path):
    doc = esf.load(path); N = doc['names']
    t = doc['tail']; p = 0
    n = struct.unpack_from('<I', t, p)[0]; p += 4
    for _ in range(n):
        l = struct.unpack_from('<H', t, p)[0]; p += 2 + 2*l + 4
    n = struct.unpack_from('<I', t, p)[0]; p += 4; asc = {}
    for _ in range(n):
        l = struct.unpack_from('<H', t, p)[0]; p += 2
        s = t[p:p+l].decode('latin-1'); p += l
        asc[struct.unpack_from('<I', t, p)[0]] = s; p += 4
    for nm in ['FACTION','CHARACTER','MILITARY_FORCE','REGION','REGION_SLOT','BUILDING','SETTLEMENT']:
        print(f'{nm:15s}', len(_find(doc['root'], nm, N, [])))
    print('factions:')
    for f in _find(doc['root'], 'FACTION', N, []):
        k = next((x for x in f.kids if isinstance(x, Val) and x.t == 0x0f), None)
        if k: print('  ', asc.get(struct.unpack('<I', k.raw)[0]))

if __name__ == '__main__':
    a = sys.argv[1:]
    {'unpack': lambda: unpack(a[1], a[2]),
     'pack': lambda: pack(a[1], a[2], a[3]),
     'summary': lambda: summary(a[1])}[a[0]]()
