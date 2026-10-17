#!/usr/bin/env python3
"""robots.txt and sitemap.xml for docs.airacegp.com. WRITTEN BEFORE THE FILES.

The owner (2026-10-17) asked for both on the website. airacegp.com already serves them (airace-web's _verify_legal.py rows 6e
and 6f hold them); docs.airacegp.com is a separate host, so it needs its own: a robots.txt is read per host, and a sitemap may
only list URLs on the host that serves it. Before this check the docs host answered 404 for both.

Same owner decision as the main site (2026-10-03, kept in the 2026-10-10 refresh): search engines and AI assistants are
welcome. So:

  1 robots.txt
    1a exists at the site root, as plain directives (not a saved error page);
    1b nothing is disallowed: the pages need their css, js and images to be read as the pages they are;
    1c every crawler may read everything: User-agent * and the AI crawlers the main site names (GPTBot, ClaudeBot, ...);
    1d names the sitemap by its absolute URL on THIS host.
  2 sitemap.xml
    2a is well-formed XML: a urlset in the sitemaps.org namespace, at least one url;
    2b every loc is an absolute https URL on docs.airacegp.com, with no query, no fragment, no space, listed once;
    2c every loc is the CANONICAL URL of a real page in this folder, resolved the way GitHub Pages resolves it (so the sitemap
       and the page never name the same page two ways);
    2d every page that may be indexed is listed (a page added later and forgotten fails here), and no page that must not be
       (404.html, the noindex redirect stub) is;
    2e every lastmod is a real date (YYYY-MM-DD), not in the future, and not before the page's own first appearance in the
       site's life (2026-09-01).
  3 served: both files come back 200 from this folder served the way GitHub Pages serves it (nothing hides them: no leading
    underscore or dot, no _config.yml that excludes them), as plain text and XML.

    python3 _verify_seo.py
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import sys
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = 'docs.airacegp.com'
ORIGIN = 'https://' + HOST
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
# The crawlers airacegp.com's robots.txt names one by one. The docs welcome the same ones.
AI_CRAWLERS = ('GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'PerplexityBot',
               'Google-Extended', 'Applebot-Extended')
SITE_BEGAN = dt.date(2026, 9, 1)
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail and not ok else ''))
    if not ok:
        fails.append(name)


def read(name):
    path = os.path.join(HERE, name)
    return open(path, encoding='utf-8').read() if os.path.exists(path) else None


# ── 1 robots.txt ────────────────────────────────────────────────────────────────────────────────────────────────
robots = read('robots.txt')
DIRECTIVE = re.compile(r'^(User-agent|Allow|Disallow|Sitemap|Crawl-delay)\s*:\s*\S.*$', re.I)
if robots is None:
    for n in ('1a robots.txt exists at the site root, as plain directives', '1b nothing is disallowed',
              '1c every crawler may read everything, the AI crawlers included', '1d names the sitemap by its absolute URL on this host'):
        check(n, False, 'robots.txt does not exist')
else:
    lines = [l.strip() for l in robots.splitlines() if l.strip() and not l.strip().startswith('#')]
    stray = [l for l in lines if not DIRECTIVE.match(l)]
    check('1a robots.txt exists at the site root, as plain directives', bool(lines) and not stray and '<' not in robots,
          f'not a directive: {stray[:2]}')
    disallows = [l for l in lines if re.match(r'(?i)disallow\s*:\s*\S', l)]
    check('1b nothing is disallowed', not disallows, f'disallowed: {disallows[:3]}')
    groups = {}
    current = []
    for l in lines:
        m = re.match(r'(?i)(user-agent|allow|disallow)\s*:\s*(.*)$', l)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if key == 'user-agent':
            if current and groups.get(current[-1], {}).get('rules'):
                current = []                                 # a new group starts after the previous group's rules
            current.append(val)
            groups.setdefault(val, {'rules': []})
        else:
            for agent in current:
                groups[agent]['rules'].append((key, val))
    wanted = ('*',) + AI_CRAWLERS
    open_to = [a for a in wanted if ('allow', '/') in [(k, v) for k, v in groups.get(a, {}).get('rules', [])]]
    check('1c every crawler may read everything, the AI crawlers included', open_to == list(wanted),
          f'no "Allow: /" for: {[a for a in wanted if a not in open_to]}')
    sitemap_lines = [l.split(':', 1)[1].strip() for l in lines if l.lower().startswith('sitemap')]
    check('1d names the sitemap by its absolute URL on this host', sitemap_lines == [ORIGIN + '/sitemap.xml'], sitemap_lines)

# ── 2 sitemap.xml ───────────────────────────────────────────────────────────────────────────────────────────────
sitemap = read('sitemap.xml')
urls = []                                                    # (loc, lastmod)
root = None
if sitemap is not None:
    try:
        root = ET.fromstring(sitemap)
    except ET.ParseError as exc:
        check('2a sitemap.xml is a well-formed urlset in the sitemaps.org namespace', False, f'XML error: {exc}')
    else:
        ok = root.tag == NS + 'urlset'
        for u in root.findall(NS + 'url'):
            loc = (u.findtext(NS + 'loc') or '').strip()
            mod = (u.findtext(NS + 'lastmod') or '').strip()
            urls.append((loc, mod))
        check('2a sitemap.xml is a well-formed urlset in the sitemaps.org namespace', ok and len(urls) >= 1,
              f'root {root.tag}, {len(urls)} urls')
else:
    check('2a sitemap.xml is a well-formed urlset in the sitemaps.org namespace', False, 'sitemap.xml does not exist')


def page_for(loc):
    """The file GitHub Pages serves for this URL: / -> index.html, /x -> x.html, /x.html -> x.html."""
    path = loc[len(ORIGIN):] if loc.startswith(ORIGIN) else None
    if path is None:
        return None
    path = path.split('#')[0].split('?')[0]
    if path in ('', '/'):
        return 'index.html'
    name = path.lstrip('/')
    if name.endswith('.html') and os.path.exists(os.path.join(HERE, name)):
        return name
    if os.path.exists(os.path.join(HERE, name + '.html')):
        return name + '.html'
    return None


def canonical_of(page):
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', read(page) or '')
    return m.group(1) if m else None


def noindex(page):
    return bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', read(page) or '', re.I))


locs = [l for l, _ in urls]
bad_shape = [l for l in locs if not re.fullmatch(r'https://' + re.escape(HOST) + r'/[^\s?#]*', l)]
dupes = sorted({l for l in locs if locs.count(l) > 1})
check('2b every loc is an absolute https URL on ' + HOST + ', no query, no fragment, listed once',
      bool(locs) and not bad_shape and not dupes, f'bad: {bad_shape[:3]} duplicated: {dupes[:3]}')

not_canonical = []
for loc in locs:
    page = page_for(loc)
    if page is None:
        not_canonical.append(f'{loc} (no such page)')
    elif canonical_of(page) != loc:
        not_canonical.append(f'{loc} (the page says {canonical_of(page)})')
check('2c every loc is the canonical URL of a real page in this folder', bool(locs) and not not_canonical, not_canonical[:3])

pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, '*.html')) if not os.path.basename(p).startswith('_'))
listed_pages = {page_for(l) for l in locs}
indexable = [p for p in pages if not noindex(p)]
missing = [p for p in indexable if p not in listed_pages]
forbidden = [p for p in pages if noindex(p) and p in listed_pages]
check('2d every page that may be indexed is listed, and no page that must not be',
      bool(locs) and not missing and not forbidden, f'missing: {missing} listed but noindex: {forbidden}')

today = dt.datetime.now(dt.timezone.utc).date()
bad_dates = []
for loc, mod in urls:
    try:
        d = dt.date.fromisoformat(mod) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', mod) else None
    except ValueError:
        d = None
    if d is None or d > today or d < SITE_BEGAN:
        bad_dates.append(f'{loc}: {mod!r}')
check('2e every lastmod is a real date (YYYY-MM-DD), not in the future, not before the site existed',
      bool(urls) and not bad_dates, bad_dates[:3])

# ── 3 served the way GitHub Pages serves this folder ────────────────────────────────────────────────────────────
config = read('_config.yml') or ''
hidden_by_config = [n for n in ('robots.txt', 'sitemap.xml') if re.search(r'(?m)^\s*-\s*' + re.escape(n) + r'\s*$', config)]
class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):                            # the check prints its own rows, not the server's access log
        pass


httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(_Quiet, directory=HERE))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{httpd.server_address[1]}'


def fetch(path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.headers.get_content_type(), r.read()
    except Exception as exc:                                 # noqa: BLE001
        return getattr(exc, 'code', 0), '', b''


rs, rt, rb = fetch('/robots.txt')
ss, st, sb = fetch('/sitemap.xml')
httpd.shutdown()
check('3 both files are served (200), as plain text and XML, and nothing in the Pages config hides them',
      rs == 200 and rt == 'text/plain' and ss == 200 and st in ('application/xml', 'text/xml') and not hidden_by_config
      and not any(n.startswith(('_', '.')) for n in ('robots.txt', 'sitemap.xml')),
      f'robots {rs} {rt}; sitemap {ss} {st}; hidden by config: {hidden_by_config}')

print(f'\n{"ALL PASS" if not fails else f"{len(fails)} FAILED"}')
sys.exit(1 if fails else 0)
