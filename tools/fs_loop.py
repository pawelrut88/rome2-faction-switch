"""Faction-switch loop: play several factions in one Rome II campaign by editing saves between turns.
OFFLINE TOOL; the single switch (V3) is tested in game on vanilla, the loop is NOT tested in game yet.

  python tools/fs_loop.py status SAVE
  python tools/fs_loop.py switch SAVE NEW_FACTION [--name OUT] [--campaign-dir DIR]

switch: writes a NEW save into save_games (never overwrites) in which NEW_FACTION is the human, local player and the
current human becomes AI (all human marks moved, as switch_faction.py --mode players). Fog of war and missions for
NEW_FACTION, in this order:
  1. kept, if NEW_FACTION still has its CAMPAIGN_SHROUD + CAMPAIGN_MISSION_MANAGER in SAVE (the game left them on a
     faction that turned AI: seen in test V3, Rome kept them for 2 AI turns; whether the game keeps them in its own
     saves is not checked yet);
  2. else copied from the last save where NEW_FACTION was human (stash, see below): its real vision and missions
     from when it was last played;
  3. else copied from the campaign's start file <game>/data/campaigns/<key>/startpos.esf (turn-1 vision; what V3
     tested).
Every switch first copies SAVE into the stash state/<campaign id>/<old faction>.save, as "last save where it was
human" for step 2. The campaign id is the CAMPAIGN_SETUP id string, so several campaigns don't mix.

Which save to switch from: the end-of-turn autosave (save_games/auto_save.save, written when the player presses End
Turn) is the intended one, so the old faction doesn't take a second (AI) turn in the same round. A save made during
the old faction's turn makes it finish that turn as AI on load (seen in V2/V3: Rome declared war). NOT tested yet
which of the two the autosave gives.
"""
import sys, os, argparse, shutil, tempfile, io, contextlib, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from savelib import *          # noqa: F401,F403
import switch_faction as sf

GAME = os.environ.get('FS_GAME') or r'F:\Steam\steamapps\common\Total War Rome II'   # FS_GAME: set by the exe
SAVES = os.path.join(os.environ.get('APPDATA', ''), 'The Creative Assembly', 'Rome2', 'save_games')
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.environ.get('FS_STATE') or os.path.join(HERE, 'state')   # stash of each faction's last save
# start files with harvested turn-1 missions (tools/build_mission_start.py): <campaign>_startpos.esf; used instead of
# the game's start file for a faction played for the first time, when present (missions gap fix, 2026-11-23)
MISSIONS = os.environ.get('FS_MISSIONS') or os.path.join(HERE, 'data', 'missions')

def load(path):
    td = tempfile.TemporaryDirectory(); i = os.path.join(td.name, 'i.esf')
    with contextlib.redirect_stdout(io.StringIO()): unpack(path, i)
    return Doc(i), td

def summary(D):
    cs = child(D, env(D), 'CAMPAIGN_SETUP')
    key = sval(D, cs.kids[0])
    cid = [sval(D, v) for v in cs.kids if isinstance(v, Val) and v.t == 0x0f and len(sval(D, v) or '') > 30][0]
    humans = [sval(D, el[0].kids[1]) for el in sf.players_array(D).kids if sf.is_human(D, el[0])]
    shroud = [k for k, f in factions(D).items()
              if any(isinstance(x, Rec) and D.N[x.name] == 'CAMPAIGN_SHROUD' for x in f.kids)]
    return dict(campaign=key, id=cid, local=sval(D, sf.setup_local(D)), humans=humans, with_shroud=shroud,
                first=list(factions(D))[0])

def safe_name(s): return ''.join(c if c.isalnum() or c in '-_' else '_' for c in s)

def read_pack_file(pack, inner):
    """Bytes of one file in a Rome II .pack (PFH4/PFH5), or None. Copied from rome2-bridge rome2bridge/mapdraw.py
    read_pack_file (2026-11-23; sharing rule), returns None instead of raising when the file isn't there."""
    want = inner.replace('/', '\\').lower()
    with open(pack, 'rb') as f:
        h = f.read(28)
        if len(h) < 28 or h[:3] != b'PFH': return None
        flags, _, pi_size, n_files, fi_size = struct.unpack_from('<5I', h, 4)
        ext = 20 if flags & 0x100 else 0
        f.read(ext); f.read(pi_size); idx = f.read(fi_size)
        offset = 28 + ext + pi_size + fi_size
        pos, stamp = 0, 4 if flags & 0x40 else 0
        for _ in range(n_files):
            size = struct.unpack_from('<I', idx, pos)[0]; pos += 4 + stamp
            end = idx.index(b'\0', pos); name = idx[pos:end].decode('ascii', 'replace').lower(); pos = end + 1
            if name == want: f.seek(offset); return f.read(size)
            offset += size
    return None

def mod_packs():
    """Mod packs of the game's mod list (scripts/user.script.txt), highest priority first (the earlier mod line wins,
    SHARED_KNOWLEDGE 'Pack priority'), as paths: data folder or an add_working_directory folder."""
    us = os.path.join(os.path.dirname(SAVES), 'scripts', 'user.script.txt')
    if not os.path.exists(us): return []
    raw = open(us, 'rb').read()
    txt = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8-sig', 'replace')
    import re
    dirs = [os.path.join(GAME, 'data')] + re.findall(r'add_working_directory\s+"([^"]+)"', txt)
    out = []
    for m in re.findall(r'^\s*mod\s+"([^"]+)"', txt, re.M):
        for d in dirs:
            p = os.path.join(d, m)
            if os.path.exists(p): out.append(p); break
    return out

def start_file(campaign):
    """(path, where) of the campaign's start file as the game uses it: from the first mod pack that has
    campaigns/<key>/startpos.esf (DeI keeps its own in its packs), copied to STATE/startpos/; else the game's loose
    data/campaigns/<key>/startpos.esf (vanilla)."""
    inner = 'campaigns/%s/startpos.esf' % campaign
    for p in mod_packs():
        b = read_pack_file(p, inner)
        if b:
            import hashlib
            d = os.path.join(STATE, 'startpos'); os.makedirs(d, exist_ok=True)
            out = os.path.join(d, '%s_%s.esf' % (campaign, hashlib.sha256(b).hexdigest()[:12]))
            if not os.path.exists(out):
                with open(out + '.tmp', 'wb') as f: f.write(b)
                os.replace(out + '.tmp', out)
            return out, os.path.basename(p)
    return os.path.join(GAME, 'data', 'campaigns', campaign, 'startpos.esf'), 'data folder'

def sha12(p):
    import hashlib
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]

def cmd_status(a):
    D, td = load(a.save); s = summary(D); td.cleanup()
    for k, v in s.items(): print('%-12s %s' % (k, v))
    sd = os.path.join(STATE, safe_name(s['id']))
    print('stash        %s' % (sorted(os.listdir(sd)) if os.path.isdir(sd) else 'none'))

def cmd_switch(a):
    src = os.path.abspath(a.save)
    D, td = load(src); s = summary(D); fac = factions(D); td.cleanup()
    assert a.new in fac, 'unknown faction ' + a.new
    assert len(s['humans']) == 1 and s['local'] == s['humans'][0], 'expect exactly one human = local: %s' % s
    old = s['local']; assert old != a.new, a.new + ' is already the human faction'
    sd = os.path.join(STATE, safe_name(s['id'])); os.makedirs(sd, exist_ok=True)
    stash_old = os.path.join(sd, old + '.save'); shutil.copyfile(src, stash_old)
    print('stashed', old, '->', stash_old)
    stash_new = os.path.join(sd, a.new + '.save')
    if a.new in s['with_shroud']: source = None; print(a.new, 'still has its shroud/missions in this save')
    elif os.path.exists(stash_new): source = stash_new; print('shroud/missions from', a.new + "'s last save:", source)
    else:
        if a.campaign_dir: source = os.path.join(a.campaign_dir, 'startpos.esf')
        else:
            source, where = start_file(s['campaign']); print('start file from', where, ':', source)
            # missions gap fix: a copy of THIS start file with harvested turn-1 missions, named after its hash
            ms = os.path.join(MISSIONS, '%s_%s.esf' % (s['campaign'], sha12(source)))
            if os.path.exists(ms): source = ms
            else: print('no missions file', ms)
        assert os.path.exists(source), 'start file not found: ' + source
        print('shroud/missions from the start file:', source)
    out = os.path.join(SAVES, (a.name or 'FS %s from %s' % (a.new, os.path.splitext(os.path.basename(src))[0])) + '.save')
    assert not os.path.exists(out), 'exists, not overwriting: ' + out
    order = list(fac); ti = None
    if not a.keep_turn:
        # resume with the faction AFTER the old human, so the old one (now AI) doesn't replay its turn
        ti = order.index(old) + 1
        if ti < len(order): print('turn resumes at index %d (%s), after %s' % (ti, order[ti], old))
        else:
            # wrapping to the next round (index 0, turn + 1) is not done (untested); fall back to --keep-turn:
            # the old faction, now AI, plays what is left of its turn, then the round goes on as normal
            ti = None; print('old human is last in turn order: turn index kept (the old faction ends its turn as AI)')
    sf.run(types.SimpleNamespace(src=src, dst=out, new=a.new, mode='players', shroud_from=source, party=None,
                                 info=False, repack=False, turn_index=ti))
    print('\nLOAD THIS SAVE:', os.path.basename(out))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status'); p.add_argument('save'); p.set_defaults(f=cmd_status)
    p = sub.add_parser('switch'); p.add_argument('save'); p.add_argument('new')
    p.add_argument('--name', help='save name without .save (default "FS <new> from <source>")')
    p.add_argument('--campaign-dir', help='folder holding the campaign startpos.esf (default <game>/data/campaigns/<key>)')
    p.add_argument('--keep-turn', action='store_true',
                   help="don't move the turn index (the old faction then finishes its turn as AI on load)")
    p.set_defaults(f=cmd_switch)
    a = ap.parse_args(); a.f(a)

if __name__ == '__main__': main()
