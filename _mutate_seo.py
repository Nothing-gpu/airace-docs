#!/usr/bin/env python3
"""Mutation-test _verify_seo.py in temporary copies, never live files.

Each mutation breaks ONE thing robots.txt or sitemap.xml must hold, or adds a page the sitemap must list; the check has to exit 1
and print the FAIL row for that reason (a crash is not a catch). A clean baseline is required before the mutations and again
after. Run one harness at a time.

    python3 _mutate_seo.py
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
KEEP = {'.py', '.md', '.html', '.txt', '.xml'}

# (what is broken, file, anchor (None creates the file), replacement or new content, the FAIL row that must appear)
CASES = [
    ('robots.txt blocks every crawler', 'robots.txt', 'User-agent: *\nAllow: /', 'User-agent: *\nDisallow: /', 'FAIL 1b'),
    ('robots.txt hides the css and js', 'robots.txt', 'User-agent: *\nAllow: /', 'User-agent: *\nAllow: /\nDisallow: /assets/', 'FAIL 1b'),
    ('robots.txt forgets an AI crawler', 'robots.txt', 'User-agent: ClaudeBot\nAllow: /\n\n', '', 'FAIL 1c'),
    ('an AI crawler is told to stay out', 'robots.txt', 'User-agent: GPTBot\nAllow: /', 'User-agent: GPTBot\nDisallow: /', 'FAIL 1c'),
    ('robots.txt forgets the sitemap', 'robots.txt', 'Sitemap: https://docs.airacegp.com/sitemap.xml\n', '', 'FAIL 1d'),
    ('robots.txt names the main site\'s sitemap', 'robots.txt', 'Sitemap: https://docs.airacegp.com/sitemap.xml',
     'Sitemap: https://airacegp.com/sitemap.xml', 'FAIL 1d'),
    ('robots.txt is a saved error page', 'robots.txt', '# airaceGP docs welcome', '<html><body>Not found</body></html>\n# airaceGP docs welcome', 'FAIL 1a'),
    ('the sitemap loses its namespace', 'sitemap.xml', ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', '', 'FAIL 2a'),
    ('the sitemap is cut off', 'sitemap.xml', '</urlset>', '', 'FAIL 2a'),
    ('a page is listed twice', 'sitemap.xml', '  <url><loc>https://docs.airacegp.com/setup</loc><lastmod>2026-10-03</lastmod></url>\n',
     '  <url><loc>https://docs.airacegp.com/setup</loc><lastmod>2026-10-03</lastmod></url>\n'
     '  <url><loc>https://docs.airacegp.com/setup</loc><lastmod>2026-10-03</lastmod></url>\n', 'FAIL 2b'),
    ('a loc uses http', 'sitemap.xml', '<loc>https://docs.airacegp.com/ai</loc>', '<loc>http://docs.airacegp.com/ai</loc>', 'FAIL 2b'),
    ('a loc carries a query string', 'sitemap.xml', '<loc>https://docs.airacegp.com/errors</loc>', '<loc>https://docs.airacegp.com/errors?x=1</loc>', 'FAIL 2b'),
    ('a loc is on another host', 'sitemap.xml', '<loc>https://docs.airacegp.com/setup</loc>', '<loc>https://airacegp.com/setup</loc>', 'FAIL 2b'),
    ('a loc names a page that does not exist', 'sitemap.xml', '<loc>https://docs.airacegp.com/ai</loc>', '<loc>https://docs.airacegp.com/ai-guide</loc>', 'FAIL 2c'),
    ('a loc is not the page\'s canonical URL', 'sitemap.xml', '<loc>https://docs.airacegp.com/setup</loc>', '<loc>https://docs.airacegp.com/setup.html</loc>', 'FAIL 2c'),
    ('a page is forgotten', 'sitemap.xml', '  <url><loc>https://docs.airacegp.com/troubleshooting</loc><lastmod>2026-10-03</lastmod></url>\n', '', 'FAIL 2d'),
    ('the 404 page is listed', 'sitemap.xml', '</urlset>', '  <url><loc>https://docs.airacegp.com/404.html</loc><lastmod>2026-10-03</lastmod></url>\n</urlset>', 'FAIL 2d'),
    ('the noindex redirect stub is listed', 'sitemap.xml', '</urlset>',
     '  <url><loc>https://docs.airacegp.com/recommended-setup</loc><lastmod>2026-09-27</lastmod></url>\n</urlset>', 'FAIL 2d'),
    ('a lastmod in the future', 'sitemap.xml', '<lastmod>2026-10-10</lastmod></url>\n  <url><loc>https://docs.airacegp.com/setup',
     '<lastmod>2099-01-01</lastmod></url>\n  <url><loc>https://docs.airacegp.com/setup', 'FAIL 2e'),
    ('a lastmod that is not a date', 'sitemap.xml', '<lastmod>2026-10-03</lastmod></url>\n  <url><loc>https://docs.airacegp.com/ai<',
     '<lastmod>last week</lastmod></url>\n  <url><loc>https://docs.airacegp.com/ai<', 'FAIL 2e'),
    ('a lastmod is missing', 'sitemap.xml', '<loc>https://docs.airacegp.com/errors</loc><lastmod>2026-10-10</lastmod>', '<loc>https://docs.airacegp.com/errors</loc>', 'FAIL 2e'),
    ('a new page is added and the sitemap is not told', 'newpage.html', None,
     '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" /><title>New</title>'
     '<link rel="canonical" href="https://docs.airacegp.com/newpage" /></head><body>New page</body></html>', 'FAIL 2d'),
    ('the Pages config hides robots.txt', '_config.yml', None, 'exclude:\n  - robots.txt\n', 'FAIL 3'),
]


def main():
    failed = 0
    with tempfile.TemporaryDirectory(prefix='seo-mutations-') as td:
        site = Path(td)
        for p in HERE.iterdir():
            if p.is_file() and p.suffix in KEEP:
                shutil.copy2(p, site / p.name)

        def run():
            for cache in site.rglob('__pycache__'):
                shutil.rmtree(cache)
            return subprocess.run([sys.executable, '-B', str(site / '_verify_seo.py')], capture_output=True, text=True, timeout=120)

        base = run()
        if base.returncode:
            print('FAIL baseline must pass before mutations\n' + base.stdout + base.stderr)
            return 1
        for what, name, old, new, reason in CASES:
            path = site / name
            if old is None:
                if path.exists():
                    print('ANCHOR MISS (file already exists) ' + what)
                    failed += 1
                    continue
                path.write_text(new, encoding='utf-8')
                original = None
            else:
                original = path.read_text(encoding='utf-8')
                if original.count(old) != 1 or old == new:
                    print(f'ANCHOR MISS ({original.count(old)}x) ' + what)
                    failed += 1
                    continue
                path.write_text(original.replace(old, new), encoding='utf-8')
            try:
                result = run()
                killed = result.returncode == 1 and reason in result.stdout and 'Traceback' not in result.stderr
                print(('killed    ' if killed else 'SURVIVED  ') + what + f'  -> wanted "{reason}", exit {result.returncode}')
                if not killed:
                    print(result.stdout + result.stderr)
                    failed += 1
            finally:
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original, encoding='utf-8')
        again = run()
        if again.returncode:
            print('FAIL restored baseline\n' + again.stdout + again.stderr)
            failed += 1
    print(f'\n{len(CASES) - failed}/{len(CASES)} mutations killed; restored baseline exit {again.returncode}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
