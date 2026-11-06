import re
import time

import requests
from flask import Flask, redirect, render_template as template, request, url_for

from dmc_dict import dmc_dict as dmc_colors

app = Flask(__name__)

BRACELETBOOK_URL = "https://www.braceletbook.com/patterns/{}/{}/"
REQUEST_TIMEOUT = 10  # seconds per request to braceletbook.com
CACHE_TTL = 6 * 60 * 60  # keep fetched patterns for 6 hours
CDN_CACHE_HEADER = "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"

ERRORS = {
    "invalid": "Please enter a design number, like 1024.",
    "not_found": "We couldn't find a normal or alpha pattern with that number on braceletbook.com. Check the number and try again.",
    "unavailable": "braceletbook.com didn't respond. Please try again in a minute.",
}

_svg_cache = {}


class PatternNotFound(Exception):
    pass


class PatternUnavailable(Exception):
    pass


def remove_wm_tags(svg_content):
    # This removes any <text> tag that contains the 'wm' class
    return re.sub(r'<text class="wm[01]".*?</text>', '', svg_content)


def _fetch(url):
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise PatternUnavailable(str(e)) from e
    if response.status_code == 404:
        raise PatternNotFound(url)
    if not response.ok:
        raise PatternUnavailable(f"{url} returned {response.status_code}")
    return response.text


def fetch_svgs(design_number, kind='normal'):
    """Return (pattern_svg, preview_svg) for a design, using a short-lived cache.

    preview_svg is None when braceletbook has no preview for the pattern.
    """
    key = (kind, design_number)
    cached = _svg_cache.get(key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    html_content = _fetch(BRACELETBOOK_URL.format(kind, design_number))
    match = re.search(r'https://[^"\'\s]*?pattern\.svg', html_content)
    if not match:
        raise PatternNotFound(design_number)
    pattern_url = match.group(0)
    preview_url = pattern_url.replace('pattern.svg', 'preview.svg')

    pattern_svg = remove_wm_tags(_fetch(pattern_url))
    try:
        preview_svg = remove_wm_tags(_fetch(preview_url))
    except PatternNotFound:
        preview_svg = None

    svgs = (pattern_svg, preview_svg)
    _svg_cache[key] = (time.time(), svgs)
    return svgs


def editor_path(kind, design_number):
    return f"/{'alpha' if kind == 'alpha' else 'design'}/{design_number}"


def load_or_redirect(design_number, kind):
    """Fetch a design's SVGs, or return a redirect.

    Normal and alpha patterns have separate numbers on braceletbook.com. If the number
    isn't a pattern of the requested kind but is one of the other kind, redirect to the
    same page for that kind. Otherwise redirect home with an error.
    """
    try:
        return fetch_svgs(design_number, kind), None
    except PatternUnavailable:
        error = "unavailable"
    except PatternNotFound:
        other = 'alpha' if kind == 'normal' else 'normal'
        try:
            fetch_svgs(design_number, other)
        except PatternNotFound:
            error = "not_found"
        except PatternUnavailable:
            error = "unavailable"
        else:
            path = request.path.replace(editor_path(kind, design_number), editor_path(other, design_number), 1)
            query = request.query_string.decode()
            return None, redirect(path + ('?' + query if query else ''))
    return None, redirect(url_for('index', error=error, design=design_number))


def parse_hex_codes(raw):
    """Turn 'ff0000,00ff00' into ['#ff0000', '#00ff00'], dropping anything that isn't a hex color."""
    codes = []
    for code in (raw or '').split(','):
        code = code.strip().lstrip('#').lower()
        if re.fullmatch(r'[0-9a-f]{6}|[0-9a-f]{3}', code):
            codes.append('#' + code)
    return codes


@app.route('/')
def index():
    error = ERRORS.get(request.args.get('error', ''))
    status = 404 if request.args.get('error') == 'not_found' else 200
    return template('index.html', error=error, design=request.args.get('design', '')), status


@app.route('/submit-design', methods=['POST'])
def submit_design():
    design_number = (request.form.get('design_number') or '').strip()
    if not design_number.isdigit():
        return redirect(url_for('index', error='invalid'))
    # Normal first; the editor redirects to /alpha/<n> if the number is an alpha pattern
    return redirect(editor_path('normal', int(design_number)))


@app.route('/design/<int:design_number>', defaults={'kind': 'normal'})
@app.route('/alpha/<int:design_number>', defaults={'kind': 'alpha'})
def design(design_number, kind):
    svgs, error_redirect = load_or_redirect(design_number, kind)
    if error_redirect:
        return error_redirect
    pattern_svg, preview_svg = svgs

    response = app.make_response(template(
        'design.html',
        design_number=design_number,
        kind=kind,
        base_path=editor_path(kind, design_number),
        pattern=pattern_svg,
        preview=preview_svg,
        hex_codes=parse_hex_codes(request.args.get('hex_codes')),
        dmc_colors=dmc_colors,
    ))
    response.headers['Cache-Control'] = CDN_CACHE_HEADER
    return response


@app.route('/design/<int:design_number>/palette', defaults={'kind': 'normal'})
@app.route('/alpha/<int:design_number>/palette', defaults={'kind': 'alpha'})
def palette(design_number, kind):
    svgs, error_redirect = load_or_redirect(design_number, kind)
    if error_redirect:
        return error_redirect
    pattern_svg, preview_svg = svgs

    num_colors = request.args.get('n', type=int) or 5
    num_colors = max(1, min(num_colors, 16))
    hex_codes = parse_hex_codes(request.args.get('hex_codes'))
    base_path = editor_path(kind, design_number)
    back_url = base_path
    if hex_codes:
        back_url += '?hex_codes=' + ','.join(c.lstrip('#') for c in hex_codes)

    return template(
        'colors.html',
        num_colors=num_colors,
        design_number=design_number,
        base_path=base_path,
        # Alpha patterns may have no separate preview; recolor the pattern itself instead
        preview_svg=preview_svg or pattern_svg,
        current_colors=hex_codes,
        back_url=back_url,
        colors=list(dmc_colors),
    )


@app.route('/generate-colors/<int:num_colors>', methods=['GET', 'POST'])
def colors(num_colors):
    # Old Smart Palette URL, kept so existing links and bookmarks still work.
    referrer = request.referrer or ''
    match = re.search(r'/design/(\d+)', referrer)
    if not match:
        return redirect(url_for('index'))
    return redirect(f"/design/{int(match.group(1))}/palette?n={num_colors}")


if __name__ == '__main__':
    app.run()
