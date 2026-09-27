"""The docs site does what it promises. WRITTEN FIRST, before the site.

Serves this folder the way GitHub Pages does (extensionless URLs resolve to
.html, unknown paths get 404.html) and drives every page with Playwright:

  1  every code in the app's errors.ERRORS has an element with id=<code> on
     the errors page, and that element carries the code's fix text -- read
     from the app's errors.py, never from a copy in this repo
  1b https://docs.airacegp.com/errors#AIR-208 style deep links resolve
  2  the recommended-setup callout names Ollama Cloud and gemma4:31b, and the
     /recommended-setup URL the app's onboarding spec promises reaches it
  3  every internal link and #anchor resolves to a real file and a real id
  4  every <img> loads and has non-empty alt text
  5  nothing clips or overflows at 360, 390, 768, 1280, 1440 and 1920 px:
     no element wider than its box unless it scrolls, no element sticking
     out of a parent that clips, no ellipsis actually truncating, no
     sideways page scroll
  6  no console errors, page errors or failed requests
  7  no string that looks like an API key anywhere in this repo's files
     (pages, scripts, images, the screenshot source data)
  8  no eyebrow: no short label stacked above text 1.5x its size (callouts
     and code blocks excepted), matching the marketing site

    python3 _verify_docs.py            # app at ../airarce-ui/airacee/airacee
    AIRACE_APP=/path/to/airacee/airacee python3 _verify_docs.py

Chromium: PW_CHROME, else /opt/pw-browsers/chromium-1194/chrome-linux/chrome
when it exists, else Playwright's own.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

ROOT = Path(__file__).resolve().parent
APP = Path(os.environ.get('AIRACE_APP') or (sys.argv[1] if len(sys.argv) > 1 else
           ROOT.parent / 'airarce-ui' / 'airacee' / 'airacee')).resolve()
CHROME = os.environ.get('PW_CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
WIDTHS = (360, 390, 768, 1280, 1440, 1920)
SITE = 'https://docs.airacegp.com'
# Spelled in pieces so this file does not match its own pattern.
KEYISH = re.compile(rb'sk-[A-Za-z0-9]{10,}|' + b'g' + rb'sk_|AIza[0-9A-Za-z_-]{20,}')

results: list[tuple[str, object, object]] = []


def check(name, got, want):
    results.append((name, got, want))


def load_errors():
    spec = importlib.util.spec_from_file_location('app_errors', APP / 'errors.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ERRORS


def pages():
    """The pages Pages will serve: top-level .html not starting with _ ."""
    return sorted(p.name for p in ROOT.glob('*.html') if not p.name.startswith('_'))


class PagesHandler(SimpleHTTPRequestHandler):
    """GitHub Pages' lookup: /x -> x.html, /dir/ -> dir/index.html, else 404.html."""

    def log_message(self, *_):
        pass

    def send_head(self):
        path = unquote(urlparse(self.path).path)
        rel = path.lstrip('/')
        if rel.startswith('_') or '/_' in rel:          # Jekyll never publishes these
            return self._not_found()
        target = ROOT / rel
        if target.is_dir():
            target = target / 'index.html'
        elif not target.exists() and (ROOT / (rel + '.html')).exists():
            target = ROOT / (rel + '.html')
        if not target.exists():
            return self._not_found()
        self.path = '/' + str(target.relative_to(ROOT))
        return super().send_head()

    def _not_found(self):
        body = (ROOT / '404.html').read_bytes() if (ROOT / '404.html').exists() else b'404'
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        import io
        return io.BytesIO(body)


# ── 5: the clipping measure, run in the page ──────────────────────────────
CLIP = r"""() => {
  const out = [];
  const vw = document.documentElement.clientWidth;
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      (el.classList.length ? '.' + [...el.classList].join('.') : '');
  const scrolls = cs => ['auto', 'scroll'].includes(cs.overflowX);
  const clips = cs => ['hidden', 'clip'].includes(cs.overflowX);
  if (document.documentElement.scrollWidth > window.innerWidth + 1)
    out.push('page scrolls sideways: ' + document.documentElement.scrollWidth + ' > ' + window.innerWidth);
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.display === 'contents') continue;
    if (el.closest('[aria-hidden="true"]') && el.closest('.bg-fx')) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    // (a) content wider than its box, and the box does not scroll
    if (cs.display !== 'inline' && el.scrollWidth > el.clientWidth + 1 && !scrolls(cs) && el.clientWidth > 0)
      out.push('wider than its box: ' + name(el) + ' ' + el.scrollWidth + ' > ' + el.clientWidth);
    // (b) text cut by an ellipsis
    if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1)
      out.push('ellipsis truncating: ' + name(el));
    // (c) sticking out of an ancestor that clips, or out of the viewport
    let a = el.parentElement, clipper = null, scroller = false;
    while (a && a !== document.body) {
      const acs = getComputedStyle(a);
      if (scrolls(acs)) { scroller = true; break; }
      if (clips(acs)) { clipper = a; break; }
      a = a.parentElement;
    }
    if (scroller || cs.position === 'fixed') continue;
    if (clipper) {
      const cr = clipper.getBoundingClientRect();
      if (r.left < cr.left - 1 || r.right > cr.right + 1)
        out.push('clipped by ' + name(clipper) + ': ' + name(el));
    } else if (r.right > vw + 1 || r.left < -1) {
      out.push('outside the viewport: ' + name(el) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' of ' + vw);
    }
  }
  return [...new Set(out)].slice(0, 12);
}"""

# 8: no eyebrow labels. The owner removed "smaller text above big text"
# from the marketing site; the docs match. An eyebrow is a short piece of
# text stacked directly above a sibling set at least 1.5x its size. Labels
# inside callouts and code blocks are content, not eyebrows, and stay.
EYEBROW = r"""() => {
  const out = [];
  const main = document.querySelector('main') || document.body;
  const shown = el => { const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const biggest = el => Math.max(parseFloat(getComputedStyle(el).fontSize),
    ...[...el.querySelectorAll('*')].map(c => parseFloat(getComputedStyle(c).fontSize)));
  for (const el of main.querySelectorAll('*')) {
    if (el.closest('.callout, .code, table, figure')) continue;
    // a label is text, not a box of images or paragraphs (a lone figure's
    // caption is short too, and is not an eyebrow)
    if (el.querySelector('img, figure, p, div, ul, ol, table')) continue;
    const next = el.nextElementSibling;
    if (!next || !shown(el) || !shown(next)) continue;
    const t = (el.innerText || '').trim();
    if (!t || t.length > 40) continue;
    const a = el.getBoundingClientRect(), b = next.getBoundingClientRect();
    const stacked = a.bottom <= b.top + 2 && a.left < b.right && b.left < a.right;
    if (stacked && biggest(next) >= 1.5 * parseFloat(getComputedStyle(el).fontSize))
      out.push(JSON.stringify(t) + ' above ' + next.tagName.toLowerCase() + ' ' + JSON.stringify((next.innerText || '').trim().slice(0, 30)));
  }
  return out;
}"""

LINKS = r"""() => [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))"""
IDS = r"""() => [...document.querySelectorAll('[id]')].map(e => e.id)"""
IMGS = r"""() => [...document.images].map(i => ({src: i.currentSrc || i.src,
    ok: i.complete && i.naturalWidth > 0, alt: (i.getAttribute('alt') || '').trim()}))"""


def internal(href, page):
    """(file, fragment) for a link inside this site, else None."""
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:')):
        return None
    if href.startswith(SITE):
        href = href[len(SITE):] or '/'
    elif re.match(r'^[a-z]+://', href) or href.startswith('//'):
        return None
    url = urlparse(urljoin('/' + page, href))
    path = url.path.lstrip('/')
    if path == '' or path.endswith('/'):
        path += 'index.html'
    if not (ROOT / path).exists() and (ROOT / (path + '.html')).exists():
        path += '.html'
    return path, unquote(url.fragment)


def main():
    from playwright.sync_api import sync_playwright

    # 7 first: it needs no browser.
    hits = []
    for f in sorted(ROOT.rglob('*')):
        if '.git' in f.parts or '__pycache__' in f.parts or not f.is_file():
            continue
        for m in KEYISH.finditer(f.read_bytes()):
            hits.append(f'{f.relative_to(ROOT)}: {m.group()[:12]!r}')
    check('7 no API-key-like string in any file', hits, [])

    names = pages()
    check('0 the site has its pages', [n for n in ('index.html', 'setup.html', 'ai.html',
          'errors.html', 'troubleshooting.html', '404.html') if n not in names], [])

    errors_reg = load_errors()
    srv = ThreadingHTTPServer(('127.0.0.1', 0), partial(PagesHandler, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}'

    with sync_playwright() as p:
        kw = {'executable_path': CHROME} if Path(CHROME).exists() else {}
        browser = p.chromium.launch(**kw)
        ctx = browser.new_context()
        page = ctx.new_page()
        console = []
        page.on('console', lambda m: console.append(f'{page.url}: {m.text[:160]}') if m.type == 'error' else None)
        page.on('pageerror', lambda e: console.append(f'{page.url}: {str(e)[:160]}'))
        # ERR_ABORTED is this script navigating away mid-load, not the site.
        page.on('requestfailed', lambda r: None if 'ERR_ABORTED' in (r.failure or '')
                else console.append(f'{page.url}: failed {r.url[:90]} ({r.failure})'))

        # 1: the error codes
        missing, nofix = [], []
        resp = page.goto(base + '/errors.html')
        if resp and resp.ok:
            page.wait_for_load_state('networkidle')
            for code, e in errors_reg.items():
                el = page.locator(f'[id="{code}"]')
                if el.count() != 1:
                    missing.append(code)
                    continue
                text = ' '.join(el.inner_text().split())
                # The page typesets the registry's two bits of markup --
                # `code` ticks become <code>, ASCII -> becomes an arrow --
                # so compare after the same substitution. The WORDS must match.
                want = ' '.join(e['fix'].replace('`', '').replace('->', '\u2192').split())
                if want not in text:
                    nofix.append(code)
        else:
            missing = list(errors_reg)
        check(f'1 all {len(errors_reg)} error codes have an element with that id', missing, [])
        check('1a ...and each one carries its fix text', nofix, [])
        check('1c no code is listed that the app does not have',
              sorted(set(page.evaluate(r"""() => [...document.querySelectorAll('[id^="AIR-"]')].map(e => e.id)
                                          .filter(i => /^AIR-\d+$/.test(i))""")
                         if resp and resp.ok else []) - set(errors_reg)), [])
        page.goto(base + '/errors#AIR-208')
        page.wait_for_timeout(300)
        check('1b /errors#AIR-208 lands on AIR-208',
              page.evaluate("""() => { const t = document.getElementById('AIR-208');
                  if (!t) return false; const r = t.getBoundingClientRect();
                  return r.top >= -2 && r.top < innerHeight / 2; }"""), True)

        # 2: the recommendation
        page.goto(base + '/ai.html')
        box = page.locator('#recommended-setup')
        txt = box.inner_text() if box.count() else ''
        check('2 the recommended-setup callout names Ollama Cloud', 'Ollama Cloud' in txt, True)
        check('2a ...and gemma4:31b', 'gemma4:31b' in txt, True)
        page.goto(base + '/recommended-setup')
        page.wait_for_timeout(800)
        check('2b /recommended-setup reaches the callout',
              page.url.split('/')[-1], 'ai.html#recommended-setup')
        page.goto(base + '/')
        check('2c the overview carries the recommendation too',
              all(s in page.inner_text('main') for s in ('Ollama Cloud', 'gemma4:31b')), True)

        # 3 + 4 + 5 per page
        ids_of, broken, bad_imgs, clipped, eyebrows = {}, [], [], [], []
        for name in names:
            page.goto(f'{base}/{name}')
            page.wait_for_load_state('networkidle')
            ids_of[name] = set(page.evaluate(IDS))
        for name in names:
            if name == 'recommended-setup.html':
                continue                      # a redirect; checked in 2b
            page.set_viewport_size({'width': 1280, 'height': 900})
            page.goto(f'{base}/{name}')
            page.wait_for_load_state('networkidle')
            for href in page.evaluate(LINKS):
                t = internal(href, name)
                if t is None:
                    continue
                f, frag = t
                if f not in ids_of and not (ROOT / f).exists():
                    broken.append(f'{name}: {href} (no file)')
                elif frag and frag not in ids_of.get(f, set()):
                    broken.append(f'{name}: {href} (no #{frag})')
            # lazy images load when scrolled to, so scroll to each first
            for i in range(page.locator('img').count()):
                page.locator('img').nth(i).scroll_into_view_if_needed()
                page.wait_for_timeout(60)
            page.wait_for_load_state('networkidle')
            for img in page.evaluate(IMGS):
                if not img['ok'] or not img['alt']:
                    bad_imgs.append(f"{name}: {img['src'].split('/')[-1]} ok={img['ok']} alt={bool(img['alt'])}")
            for e in page.evaluate(EYEBROW):
                eyebrows.append(f'{name}: {e}')
            for w in WIDTHS:
                page.set_viewport_size({'width': w, 'height': 900})
                page.wait_for_timeout(120)
                for c in page.evaluate(CLIP):
                    clipped.append(f'{name} @{w}: {c}')
                if w <= 768 and page.locator('#nav-toggle').count():
                    # the mobile menu, opened, must not clip either
                    page.click('#nav-toggle')
                    page.wait_for_timeout(120)
                    for c in page.evaluate(CLIP):
                        clipped.append(f'{name} @{w} menu open: {c}')
                    page.click('#nav-toggle')
        check('3 every internal link and anchor resolves', broken, [])
        check('4 every image loads and has alt text', bad_imgs, [])
        check('4a the docs show the app (screenshots present)',
              len(list((ROOT / 'img').glob('*.*'))) >= 5 if (ROOT / 'img').exists() else False, True)
        check('5 no clipping or overflow at ' + '/'.join(map(str, WIDTHS)), clipped[:15], [])
        check('6 no console errors', console[:10], [])
        check('8 no eyebrow label stacked above bigger text', eyebrows[:15], [])
        browser.close()
    srv.shutdown()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # a crash is a failure, never a pass
        results.append(('CRASH', repr(exc)[:300], 'no crash'))
    bad = 0
    for n, g, w in results:
        ok = g == w
        bad += not ok
        print(f'{n:<58} {"OK" if ok else "BROKEN"}')
        if not ok:
            for line in (g if isinstance(g, list) else [g]):
                print(f'      {line}')
    print(f'\n{len(results) - bad} of {len(results)} checks pass.')
    sys.exit(1 if bad or not results else 0)
