import re
import time

import requests
from flask import Flask, redirect, render_template as template, request, url_for

from dmc_dict import dmc_dict as dmc_colors

app = Flask(__name__)

BRACELETBOOK_URL = "https://www.braceletbook.com/patterns/normal/{}/"
REQUEST_TIMEOUT = 10  # seconds per request to braceletbook.com
CACHE_TTL = 6 * 60 * 60  # keep fetched patterns for 6 hours
CDN_CACHE_HEADER = "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"

ERRORS = {
    "invalid": "Please enter a design number, like 1024.",
    "not_found": "We couldn't find a normal pattern with that number on braceletbook.com. Check the number and try again.",
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


def fetch_svgs(design_number):
    """Return (pattern_svg, preview_svg) for a design, using a short-lived cache."""
    cached = _svg_cache.get(design_number)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    html_content = _fetch(BRACELETBOOK_URL.format(design_number))
    match = re.search(r'https://[^"\'\s]*?pattern\.svg', html_content)
    if not match:
        raise PatternNotFound(design_number)
    pattern_url = match.group(0)
    preview_url = pattern_url.replace('pattern.svg', 'preview.svg')

    svgs = (remove_wm_tags(_fetch(pattern_url)), remove_wm_tags(_fetch(preview_url)))
    _svg_cache[design_number] = (time.time(), svgs)
    return svgs


def load_or_redirect(design_number):
    """Fetch a design's SVGs, or return a redirect to the home page with an error."""
    try:
        return fetch_svgs(design_number), None
    except PatternNotFound:
        error = "not_found"
    except PatternUnavailable:
        error = "unavailable"
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
    return redirect(url_for('design', design_number=int(design_number)))


@app.route('/design/<int:design_number>')
def design(design_number):
    svgs, error_redirect = load_or_redirect(design_number)
    if error_redirect:
        return error_redirect
    pattern_svg, preview_svg = svgs

    response = app.make_response(template(
        'design.html',
        design_number=design_number,
        pattern=pattern_svg,
        preview=preview_svg,
        hex_codes=parse_hex_codes(request.args.get('hex_codes')),
        dmc_colors=dmc_colors,
    ))
    response.headers['Cache-Control'] = CDN_CACHE_HEADER
    return response


@app.route('/design/<int:design_number>/palette')
def palette(design_number):
    svgs, error_redirect = load_or_redirect(design_number)
    if error_redirect:
        return error_redirect
    _, preview_svg = svgs

    num_colors = request.args.get('n', type=int) or 5
    num_colors = max(1, min(num_colors, 16))
    hex_codes = parse_hex_codes(request.args.get('hex_codes'))
    back_url = url_for('design', design_number=design_number,
                       hex_codes=','.join(c.lstrip('#') for c in hex_codes) or None)

    return template(
        'colors.html',
        num_colors=num_colors,
        design_number=design_number,
        preview_svg=preview_svg,
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
    return redirect(url_for('palette', design_number=int(match.group(1)), n=num_colors))


if __name__ == '__main__':
    app.run()
