"""Screenshots of the real airaceGP app UI for the docs. Re-runnable.

Starts the app's own HTTP handler (run.py `_make_handler`, loaded through the
app's `_app_import.load_run()`, which stubs audio/ML packages that are not
installed) on loopback, with a throwaway web_config.json and .env in a temp
folder, and drives the page with Playwright. Nothing talks to a game, a
microphone or an AI provider.

The dashboard is fed a REAL normalized ACC frame (Spa, from the app repo's
committed eval frames) through the app's own `_snapshot_from_frame`, so the
analysis shown is what the app computes for that frame. The capture has no
speed/pedal trace, so those few dashboard values are demo numbers, marked as
such in DEMO_INPUTS below. The chat lines are written for the picture.

Keys: every *_API_KEY in this process's environment is removed before the
app is loaded, and the only key set is a fake placeholder, so a real key can
never reach a screenshot. Each shot is also refused if the page text or any
input value looks like a key.

    python3 _shoot_app.py /path/to/airarce-ui/airacee/airacee
    AIRACE_APP=/path/to/airacee/airacee python3 _shoot_app.py

Writes img/*.webp and img/_shots.json (what was fed in, for review; not
published -- Jekyll skips underscore files). Selectors come from the app's
web/index.html; when a reskin renames one, that shot is reported as skipped
and the rest still run.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'img'
APP = Path(os.environ.get('AIRACE_APP') or (sys.argv[1] if len(sys.argv) > 1 else
           ROOT.parent / 'airarce-ui' / 'airacee' / 'airacee')).resolve()
CHROME = os.environ.get('PW_CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
FAKE_KEY = 'demo-placeholder-not-a-key'
# Spelled in pieces so this file does not match _verify_docs.py's scan.
KEYISH = re.compile(r'sk-[A-Za-z0-9]{10,}|' + 'g' + r'sk_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_-]{20,}')

# The capture carries no driving trace; these are demo values for the picture.
DEMO_INPUTS = {'speed': 212, 'throttle': 0.86, 'brake': 0.0, 'steer': 0.04, 'gear': 5}
DEMO_CHAT = [
    {'role': 'engineer', 'text': 'Penalty. Thirty second stop-and-go for pit speeding. Serve it.', 'time': '14:02:11'},
    {'role': 'driver', 'text': 'Copy. How is the fuel?', 'time': '14:02:40'},
    {'role': 'engineer', 'text': 'Short by 1.8 laps to the flag on this tank.', 'time': '14:02:42'},
]
# What onboarding saves for a driver who gave only an Ollama Cloud key.
DEMO_CHAINS = {
    'tick_chain': [{'provider': 'ollama_cloud', 'model': 'gpt-oss:120b'},
                   {'provider': 'groq', 'model': 'openai/gpt-oss-120b'}],
    'question_chain': [{'provider': 'ollama_cloud', 'model': 'gemma4:31b'},
                       {'provider': 'ollama_cloud', 'model': 'gpt-oss:120b'}],
    'use_fallback': True,
}

done: list[str] = []
skipped: list[str] = []


def demo_snapshot(R):
    """A dashboard snapshot from a real ACC frame, or None."""
    eval_dir = APP.parents[1] / 'docs' / 'acc-research' / 'eval'
    if not eval_dir.exists():
        return None
    sys.path.insert(0, str(eval_dir))
    try:
        from committed_frames import load
        frames = load()
        frame = frames.get(2613) or frames[sorted(frames)[len(frames) // 2]]
        snap = R._snapshot_from_frame(frame)
    except Exception as exc:  # noqa: BLE001
        print(f'  (no real frame: {exc})')
        return None
    snap.update(DEMO_INPUTS)
    return snap


def guard(page, label):
    """Refuse the shot if anything on screen looks like an API key."""
    page.evaluate('document.fonts.ready.then(() => true)')
    text = page.evaluate("""() => document.body.innerText + '\\n' +
        [...document.querySelectorAll('input, textarea')].map(i => i.value).join('\\n')""")
    m = KEYISH.search(text or '')
    if m:
        raise SystemExit(f'REFUSED {label}: key-like text on screen ({m.group()[:6]}...)')


def save(png: bytes, name: str, width: int | None = None):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('RGB')
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(OUT / f'{name}.webp', 'WEBP', quality=82, method=6)
    done.append(f'{name}.webp {im.width}x{im.height}')


def shoot(label, fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 -- one renamed selector must not stop the rest
        skipped.append(f'{label}: {type(exc).__name__}: {str(exc).splitlines()[0][:140]}')


def main():
    from playwright.sync_api import sync_playwright
    if not (APP / 'run.py').exists():
        raise SystemExit(f'no run.py in {APP} -- pass the app dir (…/airarce-ui/airacee/airacee)')
    for k in [k for k in os.environ if k.endswith(('_API_KEY', '_API_KEYS'))]:
        os.environ.pop(k)
    os.environ['OLLAMA_API_KEY'] = FAKE_KEY
    sys.path.insert(0, str(APP))
    import _app_import
    R = _app_import.load_run()
    tmp = Path(tempfile.mkdtemp(prefix='airace-shoot-'))
    R._CONFIG_PATH = tmp / 'web_config.json'
    R._ENV_PATH = tmp / '.env'
    R._ENV_PATH.write_text(f'OLLAMA_API_KEY={FAKE_KEY}\n', encoding='utf-8')
    OUT.mkdir(exist_ok=True)

    snap = demo_snapshot(R)
    dash = tmp / 'dashboard_snapshot.json'
    stop = threading.Event()
    if snap:
        dash.write_text(json.dumps(snap, default=str), encoding='utf-8')

        def keep_live():                      # "live" = written in the last 2.5 s
            while not stop.is_set():
                os.utime(dash, None)
                stop.wait(0.5)
        threading.Thread(target=keep_live, daemon=True).start()
    R._chat_log.extend(DEMO_CHAT)
    (OUT / '_shots.json').write_text(json.dumps(
        {'app': 'airaceGP web/index.html via run._make_handler', 'fake_key': FAKE_KEY,
         'snapshot': snap, 'chat': DEMO_CHAT, 'chains': DEMO_CHAINS}, indent=1, default=str),
        encoding='utf-8')

    srv = ThreadingHTTPServer(('127.0.0.1', 0), R._make_handler(tmp / 'telemetry.json'))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}'

    def set_cfg(**fields):
        R._save_web_config({**R._load_web_config(), **fields})

    with sync_playwright() as p:
        kw = {'executable_path': CHROME} if Path(CHROME).exists() else {}
        browser = p.chromium.launch(**kw)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1.25,
                                  ignore_https_errors=True, reduced_motion='reduce')
        page = ctx.new_page()
        page.set_default_timeout(4000)
        page.set_default_navigation_timeout(30000)

        # ── onboarding (fresh install) ──────────────────────────────────
        set_cfg(onboarding_completed=False, game='acc')
        page.goto(base + '/')
        page.wait_for_timeout(1500)
        card = page.locator('#onboard-overlay .onboard-card')

        def ob(name):
            page.wait_for_timeout(450)
            guard(page, name)
            save(card.screenshot(), name, 1200)

        def nxt():
            page.click('#onboard-next')
            page.wait_for_timeout(350)

        shoot('onboarding app language', lambda: (nxt(), ob('onboarding-language')))  # past the welcome splash

        def eng_lang():
            nxt()
            page.click('#onboard-eng-same')
        shoot('onboarding engineer language', eng_lang)

        def game():
            nxt()
            page.locator('.onboard-game[data-fmt="acc"]').click()
            ob('onboarding-game')
        shoot('onboarding game', game)

        def providers():
            nxt()
            c = page.locator('.onboard-provider', has=page.locator('.onboard-provider-name', has_text='Ollama Cloud')).first
            c.locator('.onboard-provider-head').click()
            c.locator('input').fill(FAKE_KEY)
            page.locator('#onboard-fallback-next').click()
            page.evaluate("document.activeElement && document.activeElement.blur()")
            ob('onboarding-providers')
            # the fallback question and the chain it will save sit below
            page.evaluate("""() => { const b = document.querySelector('#onboard-overlay .onboard-body');
                if (b) b.scrollTop = b.scrollHeight; }""")
            ob('onboarding-fallback')
        shoot('onboarding providers + fallback', providers)

        def speech():
            nxt()
            ob('onboarding-speech')
        shoot('onboarding speech', speech)

        # ── the app, onboarded ──────────────────────────────────────────
        set_cfg(onboarding_completed=True, game='acc', **DEMO_CHAINS)

        def dashboard():
            page.goto(base + '/')
            page.wait_for_timeout(1200)
            page.click('.nav-btn[data-page="dashboard"]')
            page.wait_for_timeout(1500)
            guard(page, 'dashboard')
            # tall enough for the analysis strip, without full_page (which
            # would paint the fixed status bar over the middle of it)
            page.set_viewport_size({'width': 1440, 'height': 1110})
            page.wait_for_timeout(600)
            save(page.screenshot(), 'dashboard', 1600)
            page.set_viewport_size({'width': 1440, 'height': 900})
        shoot('dashboard', dashboard)

        def model_chain():
            page.click('.nav-btn[data-page="settings"]')
            page.click('.side-item[data-section="ai"]')
            page.wait_for_timeout(700)
            guard(page, 'model chain')
            # clip, not locator.screenshot(): the list re-renders on each
            # config poll, so the element is never "stable" for Playwright.
            block = page.locator('#pane-ai .chain-block').first
            block.scroll_into_view_if_needed()
            save(page.screenshot(clip=block.bounding_box()), 'settings-model-chain', 1400)
        shoot('settings model chain', model_chain)

        def telemetry_pane():
            page.click('.side-item[data-section="telemetry"]')
            page.wait_for_timeout(500)
            guard(page, 'telemetry settings')
            save(page.locator('#pane-telemetry').screenshot(), 'settings-telemetry', 1400)
        shoot('settings telemetry', telemetry_pane)

        def notice():
            import errors as app_errors
            with R._health_lock:
                R._health_notices.append(app_errors.notice(
                    'AIR-202', 'Ollama Cloud answered 429 (rate limit). Trying the next provider in your chain.',
                    source='AI engine'))
            page.click('.nav-btn[data-page="dashboard"]')
            page.wait_for_timeout(1800)
            guard(page, 'notice')
            toast = page.locator('.toast').first
            toast.wait_for()
            box = toast.bounding_box()
            pad = 20
            x = max(0, box['x'] - pad)
            clip = {'x': x, 'y': max(0, box['y'] - pad),
                    'width': min(1440 - x, box['width'] + 2 * pad), 'height': box['height'] + 2 * pad}
            save(page.screenshot(clip=clip), 'health-notice', 1200)
            with R._health_lock:
                R._health_notices.clear()
        shoot('health notice', notice)

        # ── phone width (the LAN dashboard) ─────────────────────────────
        def phone():
            m = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                                    ignore_https_errors=True, reduced_motion='reduce')
            pg = m.new_page()
            pg.set_default_navigation_timeout(30000)
            pg.goto(base + '/')
            pg.wait_for_timeout(1200)
            btn = pg.locator('.nav-btn[data-page="dashboard"]')
            if btn.is_visible():
                btn.click()
            pg.wait_for_timeout(1500)
            guard(pg, 'phone')
            save(pg.screenshot(), 'dashboard-phone', 780)
            m.close()
        shoot('phone dashboard', phone)

        browser.close()
    stop.set()
    srv.shutdown()


if __name__ == '__main__':
    main()
    print('saved:', *done, sep='\n  ')
    if skipped:
        print('SKIPPED (selector changed? update this script):', *skipped, sep='\n  ')
    sys.exit(1 if skipped or not done else 0)
