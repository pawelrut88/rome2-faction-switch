"""Missions harvest (2026-11-23): a new vanilla main_rome campaign as each faction (the game's own New Campaign menu,
through the rome2-bridge test runner, mod set Vanilla = only the bridge pack), saved on turn 1 with the runner's own
save() (autosave copied to save_games/"TestRun <stamp> <faction> turn 1.save"), then moved to
state/harvest/t1_<faction>.save. The runner backs up and puts back user.script.txt, preferences and auto_save.save.
Reuses the bridge's files read-only (a subclass here; nothing in rome2-bridge is changed).
usage: python tests/harvest.py [faction ...]   (default: every main_rome faction in the runner's vanilla list)"""
import sys, os, shutil, glob
sys.path.insert(0, r'F:\ROME2\Projects\rome2-bridge')
from rome2bridge import Bridge, load_config
from rome2bridge.testrun import Runner, load_factions

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'state', 'harvest')
SAVES = os.path.join(os.environ['APPDATA'], 'The Creative Assembly', 'Rome2', 'save_games')

class Harvest(Runner):
    def run_one(self, run_dir, button, label, group, faction, *a, **k):
        self._fac = faction
        return super().run_one(run_dir, button, label, group, faction, *a, **k)
    def stats(self, d, turn):
        super().stats(d, turn)
        if turn == 1:
            name = self.save(self._fac, 1)
            self.log('  harvest save: %s' % name)

def main():
    os.makedirs(OUT, exist_ok=True)
    data = load_factions('Vanilla')
    c = data['button_new_campaign_main_rome']
    want = sys.argv[1:]
    # Rome and Carthage are picked by party (rom_politics_...): one party each (missions per party not compared)
    key = {}
    for g, gd in c['groups'].items():
        for f in (gd['factions'][:1] if g in ('rom_rome', 'rom_carthage') else gd['factions']):
            key[f] = g if g in ('rom_rome', 'rom_carthage') else f
    t = [('button_new_campaign_main_rome', c['label'], g, f) for g, gd in c['groups'].items() for f in gd['factions']
         if f in key and (not want or key[f] in want) and not os.path.exists(os.path.join(OUT, 't1_%s.save' % key[f]))]
    print('targets:', [x[3] for x in t])
    if not t: return
    b = Bridge(load_config())
    r = Harvest(b)
    res = r.run('Vanilla', t, turns=0, save_every=0)
    for x in res:
        f = x['faction']
        src = glob.glob(os.path.join(SAVES, 'TestRun * %s turn 1.save' % f))
        if src:
            src = max(src, key=os.path.getmtime); dst = os.path.join(OUT, 't1_%s.save' % key[f])
            shutil.move(src, dst); print(f, 'ok', x.get('human'), os.path.getsize(dst))
        else: print(f, 'NO SAVE', x.get('error'))

if __name__ == '__main__': main()
