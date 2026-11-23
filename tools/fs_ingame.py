"""Helper for the faction switch pack (started by the game with os.execute; released as faction_switch_helper.exe).

Reads state/ingame/request.txt ("old new turn time"), waits for the game's new auto_save.save, writes a switched copy
with tools/fs_loop.py switch (NEW faction human, resumes after OLD), then writes ready.txt "READY <save name>".
The game opens Menu > Load and writes click.txt with the OK button's UI position; this posts a real click there
(SimulateClick on that OK does nothing), then on the confirm dialog's tick (tick.txt, or a fixed offset from the
centre if Lua didn't see it). Log: state/ingame/helper.log.
"""
import os, sys, time, shutil, subprocess, ctypes, traceback
from ctypes import wintypes as wt

FROZEN = getattr(sys, 'frozen', False)    # built with PyInstaller: faction_switch_helper.exe
if FROZEN:
    # released layout: <game>/faction_switch/faction_switch_helper.exe; its folder holds the run files, its parent is
    # the game folder (for data\campaigns\<key>\startpos.esf); liblzma-5.dll is bundled inside the exe
    DIR = os.path.dirname(os.path.abspath(sys.executable))
    GAME = os.path.dirname(DIR)
    os.environ['LIBLZMA'] = os.path.join(getattr(sys, '_MEIPASS', DIR), 'liblzma-5.dll')
    os.environ['FS_GAME'] = GAME
    os.environ['FS_STATE'] = os.path.join(DIR, 'state')
    os.environ['FS_MISSIONS'] = os.path.join(DIR, 'missions')
else:   # development: run from this project with Python
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DIR = os.environ.get('FS_DIR') or os.path.join(HERE, 'state', 'ingame')   # FS_DIR: set by dev_helper.cmd
SAVES = os.path.join(os.environ.get('APPDATA', ''), 'The Creative Assembly', 'Rome2', 'save_games')
AUTO = os.path.join(SAVES, 'auto_save.save')
u32 = ctypes.windll.user32

def log(s):
    with open(os.path.join(DIR, 'helper.log'), 'a') as f: f.write(time.strftime('%H:%M:%S ') + s + '\n')

REQ = None
def stale():
    """True when a newer request replaced ours (an old helper must not write into a new run's files)."""
    try: return open(os.path.join(DIR, 'request.txt')).read() != REQ
    except OSError: return True

def put(name, s):
    if stale(): raise SystemExit(0)
    tmp = os.path.join(DIR, name + '.tmp')
    with open(tmp, 'w') as f: f.write(s)
    os.replace(tmp, os.path.join(DIR, name))

def wait_file(name, timeout, wiggle=False, poke=None):
    """Wait for a file from the game. wiggle: post mouse moves (no click, the real cursor isn't moved) over the middle
    of the window meanwhile; the menu pauses the game and each ComponentMouseOn event is a frame where Lua looks."""
    p = os.path.join(DIR, name); t0 = time.time(); k = 0
    while time.time() - t0 < timeout:
        if wiggle:
            rc = wt.RECT(); u32.GetClientRect(hwnd(), ctypes.byref(rc)); k += 1
            x, y = rc.right // 2 + (k % 2) * 200 - 100, rc.bottom // 2 - 100   # over the save list
            u32.PostMessageW(hwnd(), 0x200, 0, (y << 16) | x)
        if os.path.exists(p):
            time.sleep(0.2)
            with open(p) as f: return f.read().strip()
        # poke: a file from the game with a harmless spot ('POKE x y w h rw rh'); clicking it gives the paused game's
        # Lua a frame (ComponentLClickUp) when mouse-over events don't come (long run round 3, 2026-11-23)
        if poke and k % 8 == 5 and os.path.exists(os.path.join(DIR, poke)):
            with open(os.path.join(DIR, poke)) as f: pk = f.read().strip()
            # never poke while minimized (client rect 0: the click went to 0,0) and never once the game has written
            # the file we wait for: by then Lua has selected the target save, and a poke that lands on the list
            # selects another save (user's full-screen playtest 2026-11-23 loaded a wrong save that way)
            if pk.startswith('POKE') and front('poke'):
                x, y = client_xy(pk)
                if x > 0 and y > 0: log('poke'); click(x, y, unless=p)
        time.sleep(0.2)
    return None

def hwnd():
    h = u32.FindWindowW(None, 'Total War: ROME 2')
    if not h: raise RuntimeError('game window not found')
    return h

def front(why=''):
    """Bring the game back to the front. Lua starts this exe with os.execute, which opens a cmd.exe console for a
    moment; in full screen the game loses focus to it and minimizes (user's playtest, 2026-11-23). Restores the
    window if minimized and makes it the foreground window (Alt tap: Windows lets a process take the foreground
    only after an input event)."""
    try: h = hwnd()
    except RuntimeError: return False
    if u32.IsIconic(h): u32.ShowWindow(h, 9)    # SW_RESTORE
    if u32.GetForegroundWindow() != h:
        u32.SetForegroundWindow(h)
        if u32.GetForegroundWindow() != h:
            u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)   # VK_MENU down/up
            u32.SetForegroundWindow(h)
        log('front%s: %s' % (' (' + why + ')' if why else '', 'ok' if u32.GetForegroundWindow() == h else 'FAILED'))
    return u32.GetForegroundWindow() == h

def client_xy(text):
    """'x y w h rw rh' (UI units) -> centre in client pixels, scaled like the bridge's client_pos."""
    x, y, w, h, rw, rh = [float(v) for v in text.split()[1:7]]
    rc = wt.RECT(); u32.GetClientRect(hwnd(), ctypes.byref(rc))
    return int((x + w / 2) * rc.right / (rw or rc.right)), int((y + h / 2) * rc.bottom / (rh or rc.bottom))

def click(x, y, unless=None):
    if stale(): raise SystemExit(0)
    """Posted click at client (x, y). The real cursor must hover there too (some lists ignore posted clicks
    otherwise; rome2-bridge post_click.ps1), so this moves the user's mouse."""
    front('click'); h = hwnd(); pt = wt.POINT(x, y); u32.ClientToScreen(h, ctypes.byref(pt))
    u32.SetCursorPos(pt.x, pt.y); time.sleep(0.4)
    if unless and os.path.exists(unless): log('poke skipped: %s came' % os.path.basename(unless)); return
    lp = (y << 16) | (x & 0xFFFF)
    for m, w, d in ((0x200, 0, 0.25), (0x200, 0, 0.25), (0x201, 1, 0.15), (0x202, 0, 0)):
        u32.PostMessageW(h, m, w, lp); time.sleep(d)
    log('posted click at client %d,%d' % (x, y))

def main():
    global REQ
    REQ = open(os.path.join(DIR, 'request.txt')).read(); req = REQ.split()
    # req[3] (Lua os.time) is NOT used: game Lua numbers are single floats, os.time() came back rounded to a multiple of
    # 128 s (seen 17 s in the future). The helper starts within a second of the request, so its own clock is the mark.
    old, new, turn = req[0], req[1], int(req[2]); t_req = T_START - 3
    log('request %s -> %s turn %d' % (old, new, turn))
    # the autosave: newer than the request and no longer growing
    t0 = time.time(); last = None
    while True:
        if time.time() - t0 < 5: front('start')   # the console flash from os.execute can come a moment later

        if time.time() - t0 > 90: raise RuntimeError('no new auto_save.save within 90 s')
        st = os.stat(AUTO) if os.path.exists(AUTO) else None
        if st and st.st_mtime >= t_req - 1:
            cur = (st.st_mtime, st.st_size)
            if cur == last: break
            last = cur
        time.sleep(1)
    src = os.path.join(DIR, 'src_t%d_%s.save' % (turn, old)); shutil.copyfile(AUTO, src)
    name = 'FS %s t%d %s' % (new, turn, time.strftime('%H%M%S'))
    log('autosave copied to %s; switching' % src)
    out = os.path.join(SAVES, name + '.save')
    if stale(): log('cancelled in game before the edit'); raise SystemExit(0)
    # Popen + poll: a cancel in game (request.txt removed) stops the edit and leaves no new save behind.
    # Output goes to a file (pipes could fill up and block while we poll).
    olog = os.path.join(DIR, 'fs_loop_out.txt')
    with open(olog, 'w') as fo:
        args = ['switch', src, new, '--name', name]
        if FROZEN: cmd = [sys.executable, '--fs-loop'] + args          # the same exe runs fs_loop (see the end)
        else: cmd = [sys.executable.replace('pythonw', 'python'), os.path.join(HERE, 'tools', 'fs_loop.py')] + args
        p = subprocess.Popen(cmd, stdout=fo, stderr=subprocess.STDOUT, text=True, cwd=DIR,
                             creationflags=0x08000000)   # CREATE_NO_WINDOW
        while p.poll() is None:
            if stale():
                p.kill(); p.wait()
                if os.path.exists(out): os.remove(out)
                log('cancelled in game: save edit stopped, %s not kept' % os.path.basename(out)); raise SystemExit(0)
            time.sleep(0.5)
    text = open(olog).read()
    log('fs_loop exit %d\n%s' % (p.returncode, text))
    if stale():
        if os.path.exists(out): os.remove(out)
        log('cancelled in game after the edit: %s removed' % os.path.basename(out)); raise SystemExit(0)
    if p.returncode:
        last = [l for l in text.splitlines() if l.strip()]
        raise RuntimeError('save edit failed: ' + (last[-1][:120] if last else 'see helper.log'))
    put('ready.txt', 'READY ' + name)
    c = wait_file('click.txt', 60, wiggle=True, poke='poke.txt')
    if not c or not c.startswith('OK'): raise RuntimeError('no OK position from the game: %r' % c)
    click(*client_xy(c))
    t = wait_file('tick.txt', 6, wiggle=True)
    if t and t.startswith('TICK'): x, y = client_xy(t)
    else:   # seen at 1920x1080: tick at client (922, 497), centre (960, 540)
        rc = wt.RECT(); u32.GetClientRect(hwnd(), ctypes.byref(rc)); s = rc.bottom / 1080.0
        x, y = int(rc.right / 2 - 38 * s), int(rc.bottom / 2 - 43 * s); log('no tick.txt; using the fixed offset')
    time.sleep(0.5); click(x, y)
    log('done: loading ' + name)

if __name__ == '__main__' and sys.argv[1:2] == ['--fs-loop']:
    # child process of the exe: the save edit (fs_loop.py switch ...), so a cancel can kill it
    sys.argv = ['fs_loop'] + sys.argv[2:]
    if sys.stdout is None or sys.stderr is None:   # windowed exe: no console streams; Popen gave us a file
        sys.stdout = sys.stderr = open(os.path.join(DIR, 'fs_loop_out2.txt'), 'w')
    import fs_loop
    fs_loop.main(); raise SystemExit(0)

if __name__ == '__main__':
    T_START = time.time()
    os.makedirs(DIR, exist_ok=True)
    try: main()
    except Exception as e:
        log('ERROR ' + ''.join(traceback.format_exception(e)))
        if REQ and not os.path.exists(os.path.join(DIR, 'ready.txt')): put('ready.txt', 'ERROR %s' % e)
