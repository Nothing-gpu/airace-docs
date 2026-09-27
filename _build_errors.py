"""Regenerate the error-code reference in errors.html from the app's errors.py.

The app's errors.ERRORS is the single source of truth: every health notice
and API error the app reports carries one of its AIR-nnn codes. This writes
the list of codes (and the matching sidebar links) between the GENERATED
markers in errors.html, so the page cannot drift from the app. Everything
outside the markers is hand-written and left alone.

    python3 _build_errors.py                          # app at ../airarce-ui/airacee/airacee
    python3 _build_errors.py /path/to/airacee/airacee
    AIRACE_APP=/path/to/airacee/airacee python3 _build_errors.py

Each code gets id="AIR-nnn", so https://docs.airacegp.com/errors#AIR-208
opens on that code. _verify_docs.py checks every code is present with its fix.
"""
from __future__ import annotations

import html
import importlib.util
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / 'errors.html'
APP = Path(os.environ.get('AIRACE_APP') or (sys.argv[1] if len(sys.argv) > 1 else
           ROOT.parent / 'airarce-ui' / 'airacee' / 'airacee')).resolve()
LEVEL = {'error': 'Error', 'warn': 'Warning', 'info': 'Info'}
MARK = ('<!-- BEGIN GENERATED {0} by _build_errors.py: do not edit by hand -->',
        '<!-- END GENERATED {0} -->')


def load_errors():
    spec = importlib.util.spec_from_file_location('app_errors', APP / 'errors.py')
    if spec is None or not (APP / 'errors.py').exists():
        raise SystemExit(f'no errors.py in {APP} -- pass the app dir (.../airarce-ui/airacee/airacee)')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ERRORS


def slug(area: str) -> str:
    return 'area-' + re.sub(r'[^a-z0-9]+', '-', area.lower()).strip('-')


def text(s: str) -> str:
    """Escape, then typeset the two bits of markup the registry uses:
    `code` spans and ASCII arrows."""
    out = html.escape(s, quote=False).replace('-&gt;', '&rarr;')
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', out)


def groups(errors):
    out: dict[str, list[tuple[str, dict]]] = {}
    for code, e in errors.items():
        out.setdefault(e['area'], []).append((code, e))
    return out


def render_body(errors) -> str:
    g = groups(errors)
    lines = ['  <h2 id="areas">By area <a class="h-anchor" href="#areas" aria-label="Link to this section">#</a></h2>',
             '  <ul class="areas">']
    for area, items in g.items():
        rng = items[0][0] if len(items) == 1 else f'{items[0][0]}&ndash;{items[-1][0][4:]}'
        lines.append(f'    <li><a href="#{slug(area)}">{html.escape(area)} <span class="r">{rng}</span></a></li>')
    lines.append('  </ul>')
    lines.append('  <nav class="codes-index" aria-label="All codes">')
    lines += [f'    <a href="#{c}">{c}</a>' for c in errors]
    lines.append('  </nav>')
    for area, items in g.items():
        sid = slug(area)
        lines.append(f'  <h2 id="{sid}">{html.escape(area)} '
                     f'<a class="h-anchor" href="#{sid}" aria-label="Link to this section">#</a></h2>')
        for code, e in items:
            lvl = e['level']
            lines += [
                f'  <article class="err" id="{code}" aria-labelledby="{code}-t">',
                '    <div class="err-head">',
                f'      <a class="err-code" href="#{code}" aria-label="Link to {code}">{code}</a>',
                f'      <h3 id="{code}-t">{text(e["title"])}</h3>',
                f'      <span class="lvl {lvl}">{LEVEL.get(lvl, lvl.title())}</span>',
                '    </div>',
                '    <dl>',
                '      <dt>What happened</dt>',
                f'      <dd>{text(e["cause"])}</dd>',
                '      <dt>What to do</dt>',
                f'      <dd class="fix">{text(e["fix"])}</dd>',
                '    </dl>',
                '  </article>',
            ]
    return '\n'.join(lines)


def render_side(errors) -> str:
    items = ['            <li><a href="#areas">By area</a></li>']
    items += [f'            <li><a href="#{slug(a)}">{html.escape(a)}</a></li>' for a in groups(errors)]
    return '\n'.join(items)


def splice(page: str, name: str, content: str) -> str:
    start, end = (m.format(name) for m in MARK)
    pat = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if not pat.search(page):
        raise SystemExit(f'errors.html has no {name} markers')
    return pat.sub(lambda _m: f'{start}\n{content}\n{" " * 12 if name == "SIDEBAR" else "  "}{end}', page)


def main():
    errors = load_errors()
    page = PAGE.read_text(encoding='utf-8')
    page = splice(page, 'CODES', render_body(errors))
    page = splice(page, 'SIDEBAR', render_side(errors))
    page = re.sub(r'(<span id="code-count">)\d+(</span>)', rf'\g<1>{len(errors)}\g<2>', page)
    PAGE.write_text(page, encoding='utf-8')
    print(f'errors.html: {len(errors)} codes in {len(groups(errors))} areas from {APP / "errors.py"}')


if __name__ == '__main__':
    main()
