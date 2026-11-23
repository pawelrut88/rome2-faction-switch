"""Missions gap fix (2026-11-23): build a copy of the campaign start file in which each harvested faction's (empty)
CAMPAIGN_MISSION_MANAGER is replaced by the filled one the game made for it in a turn-1 save of a campaign started
as that faction (victory missions + chapter mission). fs_loop then copies shroud + missions from this file instead
of the game's start file when a faction is played for the first time. NOT TESTED IN GAME until NOTES.md says so.

  python tools/build_mission_start.py VANILLA_startpos.esf OUT_startpos.esf TURN1_1.save [TURN1_2.save ...]
Each save must be turn 1 with exactly one human = its local faction. Missions name factions, provinces, buildings
and techs by key (checked on Rome's, 2026-11-23), so they don't depend on the turn order of the campaign.
The output is diffed against the source start file: only those factions' CAMPAIGN_MISSION_MANAGERs may differ.
"""
import sys, os, tempfile, copy, io, contextlib, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from savelib import *          # noqa: F401,F403
from switch_faction import _remap, setup_local, players_array, is_human
import esf

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

def mm_index(D, f):
    r = [i for i, x in enumerate(f.kids) if isinstance(x, Rec) and D.N[x.name] == 'CAMPAIGN_MISSION_MANAGER']
    assert len(r) == 1; return r[0]

def n_missions(D, mm): return len(child(D, mm, 'MISSIONS').kids)

def load(p, td, name):
    i = os.path.join(td, name)
    with contextlib.redirect_stdout(io.StringIO()): unpack(p, i)
    return Doc(i)

def main():
    src, dst, saves = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3:]
    assert src != dst and saves; h0 = sha(src)
    done = []
    with tempfile.TemporaryDirectory() as td:
        D = load(src, td, 'start.esf'); facs = factions(D)
        for n, sp in enumerate(saves):
            S = load(sp, td, 's%d.esf' % n)
            key = sval(S, setup_local(S))
            humans = [sval(S, el[0].kids[1]) for el in players_array(S).kids if is_human(S, el[0])]
            assert humans == [key], (sp, 'humans', humans, 'local', key)
            w = find(S, env(S), 'WORLD', maxd=2)[0]
            sf = factions(S)[key]; smm = sf.kids[mm_index(S, sf)]
            k = n_missions(S, smm); assert k > 0, (sp, key, 'no missions')
            df = facs[key]; di = mm_index(D, df)
            assert n_missions(D, df.kids[di]) == 0, (key, 'start file already has missions')
            mm = copy.deepcopy(smm); _remap(S, D, mm)
            df.kids[di] = mm; df.szraw = None
            done.append(key); print('%-22s %d missions from %s' % (key, k, os.path.basename(sp)))
        assert len(set(done)) == len(done), 'a faction twice'
        D.finish(); b = os.path.join(td, 'out.esf'); esf.save(D.d, b); pack(src, b, dst)
    assert sha(src) == h0
    with tempfile.TemporaryDirectory() as td:
        A, B = load(src, td, 'x.esf'), load(dst, td, 'y.esf')
        order = list(factions(A)); ok = {'/FACTION_ARRAY[%d].0/FACTION' % order.index(k) for k in done}
        out = diff(A, A.d['root'], B, B.d['root'])
        bad = [p for p, _ in out if not any(e in p for e in ok)]
        assert not bad, ('UNEXPECTED differences', bad[:10])
        for k in done: assert n_missions(B, factions(B)[k].kids[mm_index(B, factions(B)[k])]) > 0
    print('wrote', dst, sha(dst), '(%d factions)' % len(done))

if __name__ == '__main__': main()
