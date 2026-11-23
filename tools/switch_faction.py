"""Make a COPY of a Rome II save with another faction as the played (human) faction.  OFFLINE ONLY: not tested in game.

  python tools/switch_faction.py SRC.save DST.save NEW_FACTION [--mode local|players] [--party KEY]
  python tools/switch_faction.py SRC.save --info           (show the human faction fields, change nothing)
  python tools/switch_faction.py SRC.save DST.save --repack (control: no edit, only decompress + recompress)

--mode local   (default) change only CAMPAIGN_ENV/CAMPAIGN_SETUP_LOCAL[0] = the local player's faction key.
               This is the edit reported on Steam (Komandir Kronos, EditSF): the save loads as the new faction, but
               the turn waits forever on the old human faction.
--mode players also move the "human" marks of the player setup from the old to the new faction, in BOTH copies:
               CAMPAIGN_SETUP/CAMPAIGN_PLAYERS_SETUP/PLAYERS_ARRAY[i]/CAMPAIGN_PLAYER_SETUP and
               FACTION/CAMPAIGN_PLAYER_SETUP (each FACTION record carries its own copy). Fields, from diffing turn-1
               saves of the same campaign played as different factions:
                 INGAME_MODIFIABLES[0..2] u8   player index (0 or 1) human / ff AI
                 INGAME_MODIFIABLES[3]   uint 1 human / 0 AI
                 [2] bool                       true human / false AI
                 [6] string                     chosen political party key (human) / '' (AI)
               NOT changed (human-only data the game creates at campaign start; a script can't make them):
               FACTION/CAMPAIGN_SHROUD (+ its presence flag), FACTION/CAMPAIGN_MISSION_MANAGER, a few unnamed faction
               values, and the turn order (the human faction is moved to FACTION_ARRAY[0] at campaign start;
               region owners etc. refer to factions by that index, so reordering is not attempted).
The SAVE_GAME_HEADERs (save-menu name, flag, minimap) are left as they are.
The source file is never written. The result is decompressed again and diffed against the source; the script fails
if anything other than the intended fields changed.
"""
import sys, os, argparse, tempfile, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from savelib import *          # noqa: F401,F403
import esf

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

def setup_local(D): return child(D, env(D), 'CAMPAIGN_SETUP_LOCAL').kids[0]

def players_array(D):
    cs = child(D, env(D), 'CAMPAIGN_SETUP')
    return child(D, child(D, cs, 'CAMPAIGN_PLAYERS_SETUP'), 'PLAYERS_ARRAY')

def player_setups(D, key):
    """Both CAMPAIGN_PLAYER_SETUP records of a faction: (PLAYERS_ARRAY copy, FACTION copy)."""
    a = [el[0] for el in players_array(D).kids if sval(D, el[0].kids[1]) == key]
    assert len(a) == 1, ('PLAYERS_ARRAY entries for', key, len(a))
    f = child(D, factions(D)[key], 'CAMPAIGN_PLAYER_SETUP')
    # The copies match except field [5] (u24 0x03bff7 in PLAYERS_ARRAY, 0 in the FACTION copy, for every faction
    # seen); compare the rest.
    d = [p for p, _ in diff(D, a[0], D, f) if p != '/CAMPAIGN_PLAYER_SETUP.5']
    assert not d, key + ': the two player-setup copies differ (%s); layout not understood, stopping' % d
    return a[0], f

def human_fields(D, ps):
    m = ps.kids[0]
    assert D.N[m.name] == 'CAMPAIGN_PLAYER_SETUP_INGAME_MODIFIABLES' and len(ps.kids) == 7, 'unexpected layout'
    return [(m.kids, 0), (m.kids, 1), (m.kids, 2), (m.kids, 3), (ps.kids, 2), (ps.kids, 6)]

def is_human(D, ps):
    # MODIFIABLES[0..2] hold a player index (01 in one save, 0 = type 0x19 in older ones), ff for AI; so test the
    # human bool [2] (0x12 true) and MODIFIABLES[3] (0x15 = 1).
    m = ps.kids[0].kids
    return ps.kids[2].t == 0x12 and m[3].t == 0x15 and m[0].raw != b'\xff'

def leader_party(D, key):
    # party key of the faction's first character (taken as the default party for a newly human faction)
    for c in find(D, factions(D)[key], 'CHARACTER_DETAILS', maxd=6):
        for v in c.kids:
            if isinstance(v, Val) and v.t == 0x0f and (sval(D, v) or '').startswith(key.split('_')[0] + '_politics_'):
                return sval(D, v)
    raise SystemExit('no party key found for %s; pass --party' % key)

def vi_u8(v):
    return 0 if v.t == 0x19 else v.raw[0]

def _remap(S, D, node):
    """Re-point record names and string-table indices of a node copied from doc S into doc D (in place)."""
    if isinstance(node, Rec):
        nm = S.N[node.name]
        if nm not in D.N: D.N.append(nm)
        node.name = D.N.index(nm)
        if node.name > 0x1ff: node.long = True
        node.szraw = None; node.cntraw = None; node.elraw = None
        for k in kids(node): _remap(S, D, k)
    elif isinstance(node, Val) and node.t == 0x0f:
        node.raw = struct.pack('<I', D.asc(S.i2a[struct.unpack('<I', node.raw)[0]]))
    elif isinstance(node, Arr) and node.t == 0x4f:
        node.raw = b''.join(struct.pack('<I', D.asc(S.i2a[struct.unpack_from('<I', node.raw, i)[0]]))
                            for i in range(0, len(node.raw), 4))
    elif (isinstance(node, Val) and node.t == 0x0e) or (isinstance(node, Arr) and node.t == 0x4e):
        su = {x: t for t, x in S.tb['u16']}; du = {t: x for t, x in D.tb['u16']}
        def u(i):
            s = su[i]
            if s not in du:
                n = max([x for _, x in D.tb['u16']] or [-1]) + 1; D.tb['u16'].append((s, n)); du[s] = n
            return du[s]
        node.raw = b''.join(struct.pack('<I', u(struct.unpack_from('<I', node.raw, i)[0])) for i in range(0, len(node.raw), 4))

def copy_human_records(D, key, startpos):
    """Copy CAMPAIGN_MISSION_MANAGER and CAMPAIGN_SHROUD of faction `key` from a start file into the save's FACTION
    record, at the same places (after GOVERNMENT / after MORGUE + flag), and set the shroud flag. Returns the
    faction's FACTION_ARRAY index."""
    # `startpos` may also be an earlier SAVE in which `key` was human (same layout). Returns None (no change) when the
    # faction already has both records in this save.
    import copy, io, contextlib
    names = lambda doc, f: [doc.N[x.name] if isinstance(x, Rec) else None for x in f.kids]
    df = factions(D)[key]; dn = names(D, df)
    have = ('CAMPAIGN_SHROUD' in dn, 'CAMPAIGN_MISSION_MANAGER' in dn)
    if all(have):
        print(key, 'already has CAMPAIGN_SHROUD and CAMPAIGN_MISSION_MANAGER in this save: kept'); return None
    assert not any(have), key + ' has only one of shroud/missions in the save; layout not understood'
    with tempfile.TemporaryDirectory() as td:
        si = os.path.join(td, 's.esf')
        with contextlib.redirect_stdout(io.StringIO()): unpack(startpos, si)
        S = Doc(si)
    sf = factions(S)[key]; sn = names(S, sf)
    assert 'CAMPAIGN_SHROUD' in sn and 'CAMPAIGN_MISSION_MANAGER' in sn, key + ' has no shroud/missions in ' + startpos
    # start file: ... GOVERNMENT, MISSION_MANAGER, key ... MORGUE, bool(true), SHROUD, religion ...
    gi, mi = sn.index('GOVERNMENT'), sn.index('CAMPAIGN_MISSION_MANAGER'); assert mi == gi + 1
    mo, sh = sn.index('MORGUE'), sn.index('CAMPAIGN_SHROUD'); assert sh == mo + 2 and sf.kids[mo + 1].t == 0x12
    dmo = dn.index('MORGUE'); assert df.kids[dmo + 1].t == 0x13, 'save shroud flag is not false'
    shroud = copy.deepcopy(sf.kids[sh]); _remap(S, D, shroud)
    mm = copy.deepcopy(sf.kids[mi]); _remap(S, D, mm)
    # insert later position first so earlier indices stay valid
    df.kids[dmo + 1] = Val(0x12, b''); df.kids.insert(dmo + 2, shroud)
    df.kids.insert(dn.index('GOVERNMENT') + 1, mm)
    df.szraw = None
    print('copied CAMPAIGN_SHROUD (%d bytes) and CAMPAIGN_MISSION_MANAGER (%d bytes) for %s from %s'
          % (len(shroud.enc()), len(mm.enc()), key, startpos))
    return list(factions(D)).index(key)

REVEAL_RADIUS = 12   # display units around each army/agent/settlement (the game's LINE_OF_SIGHT boxes: ~5-6 each way)

def reveal_shroud(D, key, points, radius=REVEAL_RADIUS):
    """Mark the area around `points` (display x, y of the faction's characters and settlements, written by the game
    at switch time) as explored and visible (shroud arrays 0 and 1). A faction played for the first time gets its
    turn-1 shroud, and any faction's AI-moved armies and fleets can stand in land or sea it never saw: there they
    were hidden and could not be selected (user's playtest 2026-11-23). Returns the FACTION_ARRAY index or None."""
    import shroud
    f = factions(D)[key]
    sh = [x for x in f.kids if isinstance(x, Rec) and D.N[x.name] == 'CAMPAIGN_SHROUD']
    if not sh: print('no CAMPAIGN_SHROUD for', key, '- nothing revealed'); return None
    qs = [q for q in sh[0].kids if isinstance(q, Rec) and D.N[q.name] == 'QUAD_TREE_BIT_ARRAY']
    assert len(qs) == 3, 'CAMPAIGN_SHROUD layout not understood'
    for i in (0, 1):
        v = qs[i].kids[3]; dims = [struct.unpack('<H', x.raw)[0] for x in qs[i].kids[:3]]
        assert dims == [1357, 1110, 2048], 'shroud size not understood: %s' % dims
        v.raw, n = shroud.reveal(v.raw, points, radius)
        print('shroud array %d of %s: %d cells set around %d positions' % (i, key, n, len(points)))
    return list(factions(D)).index(key)

def info(D):
    print('CAMPAIGN_SETUP_LOCAL:', sval(D, setup_local(D)))
    order = list(factions(D)); print('FACTION_ARRAY[0] (first in turn order):', order[0], ' factions:', len(order))
    for el in players_array(D).kids:
        ps = el[0]
        if is_human(D, ps): print('human in PLAYERS_ARRAY:', sval(D, ps.kids[1]), 'party', repr(sval(D, ps.kids[6])))
    for k, f in factions(D).items():
        if [x for x in f.kids if isinstance(x, Rec) and D.N[x.name] == 'CAMPAIGN_SHROUD']: print('has CAMPAIGN_SHROUD:', k)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst', nargs='?'); ap.add_argument('new', nargs='?')
    ap.add_argument('--mode', choices=['local', 'players', 'both'], default='local',
                    help='both = the old faction stays human too (two humans; local = the new one)')
    ap.add_argument('--shroud-from', help='start file (startpos.esf) to copy the new faction\'s CAMPAIGN_SHROUD and '
                    'CAMPAIGN_MISSION_MANAGER from (with the shroud flag after MORGUE)')
    ap.add_argument('--party'); ap.add_argument('--info', action='store_true'); ap.add_argument('--repack', action='store_true')
    run(ap.parse_args())

def run(a):
    """a: namespace with src, dst, new, mode, shroud_from, party, info, repack (see main)."""
    src = os.path.abspath(a.src); h0 = sha(src)
    with tempfile.TemporaryDirectory() as td:
        orig, new = os.path.join(td, 'orig.esf'), os.path.join(td, 'new.esf')
        unpack(src, orig); D = Doc(orig)
        if a.info: info(D); return
        dst = os.path.abspath(a.dst); assert dst != src, 'refusing to overwrite the source'
        expect = set()
        if not a.repack:
            fac = factions(D); assert a.new in fac, 'unknown faction ' + a.new
            sl = setup_local(D); old = sval(D, sl); assert old != a.new, 'already the local faction'
            print('local faction', old, '->', a.new)
            sl.raw = struct.pack('<I', D.asc(a.new)); expect.add('/CAMPAIGN_SETUP_LOCAL.0')
            if a.mode in ('players', 'both'):
                po, pn = player_setups(D, old), player_setups(D, a.new)
                assert is_human(D, po[0]) and not is_human(D, pn[0]), 'old faction not human or new one already human'
                old_party = sval(D, po[0].kids[6])
                # party: --party, else '' when the old human had none (vanilla), else the new faction's leader's party
                party = a.party if a.party is not None else ('' if not old_party else leader_party(D, a.new))
                print('party for', a.new, ':', repr(party))
                ho, hn = human_fields(D, po[0]), human_fields(D, pn[0])
                vals_h = [lst[i] for lst, i in ho]; vals_ai = [lst[i] for lst, i in hn]
                import copy
                for recs in (po, pn):
                    for r in recs: r.szraw = None
                for rec_o, rec_n in zip(po, pn):
                    for (lo, io), (ln, i_n), vh, va in zip(human_fields(D, rec_o), human_fields(D, rec_n), vals_h, vals_ai):
                        if a.mode == 'players': lo[io] = copy.copy(va)
                        ln[i_n] = copy.copy(vh)
                    if a.mode == 'both':
                        # second human: player index 1 if the first is 0, else 0 (MODIFIABLES[0..2])
                        oi = vi_u8(rec_o.kids[0].kids[0]); ni = 0 if oi else 1
                        for j in range(3): rec_n.kids[0].kids[j] = Val(0x1a, bytes([ni])) if ni else Val(0x19, b'')
                    rec_n.kids[6] = Val(0x0f, struct.pack('<I', D.asc(party)))
                    if a.mode == 'players': rec_o.kids[6] = Val(0x0f, struct.pack('<I', D.asc('')))
                expect |= {'CAMPAIGN_PLAYER_SETUP'}
            ti = getattr(a, 'turn_index', None)
            if ti is not None:
                # WORLD[1] = FACTION_ARRAY index of the faction whose turn it is (0 on Rome's turn, 1 on Carthage's,
                # in vanilla saves 2026-11-22). Written in the game's compact uint forms.
                w = find(D, env(D), 'WORLD', maxd=2)[0]; v = w.kids[1]
                assert isinstance(v, Val) and v.t in (0x14, 0x15, 0x16, 0x17, 0x08), 'WORLD[1] not a uint'
                w.kids[1] = (Val(0x14, b'') if ti == 0 else Val(0x15, b'') if ti == 1 else
                             Val(0x16, bytes([ti])) if ti < 256 else Val(0x17, struct.pack('<H', ti)))
                w.szraw = None; expect.add('/WORLD.1'); print('turn index (WORLD[1]) ->', ti)
            if a.shroud_from:
                idx = copy_human_records(D, a.new, a.shroud_from)
                if idx is not None: expect.add('/FACTION_ARRAY[%d].0/FACTION' % idx)
            if getattr(a, 'reveal', None):
                idx = reveal_shroud(D, a.new, a.reveal)
                if idx is not None: expect.add('/FACTION_ARRAY[%d].0/FACTION' % idx)
            D.finish()
        esf.save(D.d, new)
        pack(src, new, dst)
    assert sha(src) == h0, 'source changed!'
    # verify: decompress the result and diff it against the source
    with tempfile.TemporaryDirectory() as td:
        x, y = os.path.join(td, 'x.esf'), os.path.join(td, 'y.esf')
        unpack(src, x); unpack(dst, y); A, B = Doc(x), Doc(y)
        out = diff(A, A.d['root'], B, B.d['root'])
        print('--- inner differences (%d):' % len(out))
        for p, m in out: print('  ', p, '|', m)
        bad = [p for p, _ in out if not any(e in p for e in expect)]
        if bad: raise SystemExit('UNEXPECTED differences: %s' % bad)
        oa, ob = esf.load(src), esf.load(dst)
        hdr_same = oa['root'].kids[0].enc() == ob['root'].kids[0].enc()
        print('outer SAVE_GAME_HEADER unchanged:', hdr_same, '| outer names/tail unchanged:', oa['names'] == ob['names'] and oa['tail'] == ob['tail'])
        assert hdr_same
        if not a.repack: info(B)
    print('wrote', dst, 'sha256', sha(dst), '(source', h0, 'unchanged)')

if __name__ == '__main__': main()
