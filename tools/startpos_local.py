"""Make a COPY of a campaign start file (startpos.esf) whose local (first played) faction is another one.
For harvesting turn-1 mission managers (missions gap, 2026-11-23): `rome2bridge start --campaign main_rome` plays
the start file's local faction (CAMPAIGN_ENV/CAMPAIGN_SETUP_LOCAL[0]); with this copy in place it should start as
FACTION instead. NOT TESTED IN GAME until NOTES.md says so.

  python tools/startpos_local.py SRC_startpos.esf DST_startpos.esf FACTION
The source is never written. The result is decompressed again and diffed: only CAMPAIGN_SETUP_LOCAL.0 may differ.
"""
import sys, os, tempfile, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from savelib import *          # noqa: F401,F403
import esf

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

def main():
    src, dst, key = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3]
    assert src != dst; h0 = sha(src)
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, 'a.esf'), os.path.join(td, 'b.esf')
        unpack(src, a); D = Doc(a)
        assert key in factions(D), 'unknown faction ' + key
        sl = child(D, env(D), 'CAMPAIGN_SETUP_LOCAL').kids[0]
        print('local', sval(D, sl), '->', key)
        sl.raw = struct.pack('<I', D.asc(key)); D.finish()
        esf.save(D.d, b); pack(src, b, dst)
    assert sha(src) == h0
    with tempfile.TemporaryDirectory() as td:
        x, y = os.path.join(td, 'x.esf'), os.path.join(td, 'y.esf')
        unpack(src, x); unpack(dst, y); A, B = Doc(x), Doc(y)
        out = diff(A, A.d['root'], B, B.d['root'])
        for p, m in out: print('  ', p, '|', m)
        assert [p for p, _ in out] == ['/CAMPAIGN_SETUP_LOCAL.0'] or all(p.endswith('CAMPAIGN_SETUP_LOCAL.0') for p, _ in out), out
    print('wrote', dst, sha(dst))

if __name__ == '__main__': main()
