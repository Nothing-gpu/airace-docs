#!/usr/bin/env python3
"""Legal + content check for docs.airacegp.com. WRITTEN BEFORE THE FIXES.

Same owner decisions as airacegp.com's _verify_legal.py (2026-10-03): free
forever, no personal details, a short privacy note, the Luxembourg rules
followed voluntarily, Czech law stated correctly.

  1 every page: no request to another site; a footer privacy note (no
    cookies, no analytics, GitHub's privacy statement); the full
    non-affiliation notice plus a catch-all for other brands;
  2 accessibility.html: Czech Acts 99/2019 and 424/2023, Luxembourg followed
    voluntarily, "partially compliant" until a screen-reader test, email
    contact, no owner placeholder;
  3 customizing.html documents push to talk (wheel button, hold, tap) and
    the male English voice; the home page links airacegp.com/llms.txt.
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''))
    if not ok:
        fails.append(name)


pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, '*.html')))
for p in pages:
    s = open(os.path.join(HERE, p), encoding='utf-8').read()
    if 'http-equiv="refresh"' in s:
        continue   # a redirect stub (noindex, no content): nothing to label
    third = re.findall(r'<(?:link|script|img|iframe|source)\b[^>]*\b(?:href|src)="(https?://[^"]+)"', s)
    third += re.findall(r'url\(["\']?(https?://[^)"\']+)', s)
    third = [u for u in third if not re.match(r'https?://(www\.)?(docs\.)?airacegp\.com/', u)]
    check(f'1a {p}: no request to another site', not third, str(third[:3]))
    foot = s[s.rfind('<footer'):]
    check(f'1b {p}: footer privacy note', bool(re.search(r'no cookies', foot, re.I) and re.search(r'no analytics', foot, re.I)
          and 'github-general-privacy-statement' in foot))
    check(f'1c {p}: full notice + catch-all', all(k in foot for k in (
        'trademarks of Formula One Licensing BV', 'Electronic Arts Inc. and Codemasters', 'property of their respective owners')))
    check(f'1d {p}: no owner placeholder', not re.search(r'OWNER INPUT|TODO\(owner\)', s))

a = open(os.path.join(HERE, 'accessibility.html'), encoding='utf-8').read()
check('2a Czech law + Luxembourg voluntary', all(k in a for k in ('99/2019', '424/2023', 'Luxembourg', 'voluntar')))
check('2b partially compliant until a screen-reader test', not re.search(r'fully compliant', a, re.I)
      and re.search(r'partially compliant', a, re.I) is not None)
check('2c email contact', 'mailto:contact@airacegp.com' in a)

c = open(os.path.join(HERE, 'customizing.html'), encoding='utf-8').read()
check('3a push to talk documented', all(k in c for k in ('Push to talk', 'wheel', 'Hold', 'Tap', 'Bind button')))
check('3b male English voice documented', re.search(r'male', c, re.I) is not None and 'Cori' in c)
check('3d quiet button, drink reminder and forward UDP documented', all(k in c for k in ('Quiet button', 'Drink reminder', 'Forward UDP', 'SimHub')))
check('3c home page links llms.txt', 'https://airacegp.com/llms.txt' in open(os.path.join(HERE, 'index.html'), encoding='utf-8').read())

print(f'\n{"ALL PASS" if not fails else f"{len(fails)} FAILED"}')
sys.exit(1 if fails else 0)
