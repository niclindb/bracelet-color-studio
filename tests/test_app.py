import pytest
import requests

import app as app_module

PATTERN_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><style>.s1-a{stroke:#ff0000}.s1-b{stroke:#00ff00}</style></svg>'
PREVIEW_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><style>.k-a{fill:#ff0000}.k-b{fill:#00ff00}</style><text class="wm0">watermark</text></svg>'
ALPHA_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><style>.k-a{fill:#fff}.k-b{fill:none}</style></svg>'
PAGE_HTML = '<img src="https://img.braceletbook.com/patterns/1024/pattern.svg">'


class FakeResponse:
    def __init__(self, text='', status_code=200):
        self.text = text
        self.status_code = status_code
        self.ok = status_code < 400


@pytest.fixture
def client():
    app_module._svg_cache.clear()
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


@pytest.fixture
def braceletbook(monkeypatch):
    """Fake braceletbook.com: design 1024 exists, everything else is a 404."""
    calls = []

    def fake_get(url, timeout=None):
        calls.append((url, timeout))
        if url.endswith('/patterns/alpha/555/'):
            return FakeResponse('<img src="https://img.braceletbook.com/alpha/555/pattern.svg">')
        if url.endswith('/alpha/555/pattern.svg'):
            return FakeResponse(ALPHA_SVG)
        if url.endswith('/alpha/555/preview.svg'):
            return FakeResponse(status_code=404)
        if url.endswith('/patterns/normal/1024/'):
            return FakeResponse(PAGE_HTML)
        if url.endswith('pattern.svg'):
            return FakeResponse(PATTERN_SVG)
        if url.endswith('preview.svg'):
            return FakeResponse(PREVIEW_SVG)
        return FakeResponse(status_code=404)

    monkeypatch.setattr(app_module.requests, 'get', fake_get)
    return calls


def test_home_page(client):
    assert client.get('/').status_code == 200


def test_submit_design_redirects_to_editor(client):
    response = client.post('/submit-design', data={'design_number': '1024'})
    assert response.status_code == 302
    assert response.headers['Location'] == '/design/1024'


@pytest.mark.parametrize('pasted, location', [
    ('https://www.braceletbook.com/patterns/normal/1024/', '/design/1024'),
    ('braceletbook.com/patterns/alpha/3318', '/alpha/3318'),
    ('#1024', '/design/1024'),
])
def test_submit_design_accepts_links_and_hash(client, pasted, location):
    response = client.post('/submit-design', data={'design_number': pasted})
    assert response.headers['Location'] == location


def test_submit_design_rejects_empty_number(client):
    response = client.post('/submit-design', data={'design_number': ''})
    assert response.headers['Location'] == '/?error=invalid'
    assert b'Please enter a design number' in client.get('/?error=invalid').data


def test_editor_loads_pattern_and_removes_watermark(client, braceletbook):
    response = client.get('/design/1024?hex_codes=AABBCC,zzz,123')
    assert response.status_code == 200
    body = response.data.decode()
    assert '.s1-a{stroke:#ff0000}' in body
    assert 'watermark' not in body
    # Invalid hex codes are dropped, valid ones are lowercased
    assert '["#aabbcc", "#123"]' in body
    assert 's-maxage' in response.headers['Cache-Control']
    # Every request to braceletbook.com has a timeout
    assert all(timeout for _, timeout in braceletbook)


def test_editor_caches_braceletbook_requests(client, braceletbook):
    client.get('/design/1024')
    client.get('/design/1024')
    assert len(braceletbook) == 3


def test_unknown_design_redirects_home_with_error(client, braceletbook):
    response = client.get('/design/99999')
    assert response.headers['Location'] == '/?error=not_found&design=99999'
    page = client.get('/?error=not_found&design=99999')
    assert page.status_code == 404
    assert b'normal or alpha pattern' in page.data
    assert b'value="99999"' in page.data


def test_braceletbook_down_shows_unavailable(client, monkeypatch):
    def fail(url, timeout=None):
        raise requests.Timeout('slow')

    monkeypatch.setattr(app_module.requests, 'get', fail)
    response = client.get('/design/1024')
    assert response.headers['Location'] == '/?error=unavailable&design=1024'


def test_palette_page(client, braceletbook):
    response = client.get('/design/1024/palette?n=2&hex_codes=aabbcc,ddeeff')
    assert response.status_code == 200
    body = response.data.decode()
    assert 'const numColors = 2;' in body
    assert 'const DESIGN_NUMBER = 1024;' in body
    assert 'href="/design/1024?hex_codes=aabbcc,ddeeff"' in body
    assert '.k-a{fill:#ff0000}' in body


def test_palette_clamps_color_count(client, braceletbook):
    body = client.get('/design/1024/palette?n=99').data.decode()
    assert 'const numColors = 16;' in body


def test_old_palette_url_without_referrer_does_not_crash(client):
    response = client.get('/generate-colors/5')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'


def test_old_palette_url_with_referrer_redirects(client):
    response = client.post('/generate-colors/5', headers={'Referer': 'https://example.com/design/1024?hex_codes=aa'})
    assert response.headers['Location'] == '/design/1024/palette?n=5'


def test_alpha_number_redirects_to_alpha_editor(client, braceletbook):
    # The home form always tries normal first; an alpha-only number lands on the alpha editor
    assert client.post('/submit-design', data={'design_number': '555'}).headers['Location'] == '/design/555'
    response = client.get('/design/555?hex_codes=ffffff')
    assert response.headers['Location'] == '/alpha/555?hex_codes=ffffff'


def test_alpha_palette_redirect_keeps_path(client, braceletbook):
    response = client.get('/design/555/palette?n=1')
    assert response.headers['Location'] == '/alpha/555/palette?n=1'


def test_alpha_editor_without_preview(client, braceletbook):
    response = client.get('/alpha/555')
    assert response.status_code == 200
    body = response.data.decode()
    assert '.k-a{fill:#fff}' in body
    assert 'class="preview-bar-wrapper"' not in body
    assert 'const BASE_PATH = "/alpha/555";' in body
    assert any('/patterns/alpha/555/' in url for url, _ in braceletbook)


def test_alpha_palette_uses_pattern_when_no_preview(client, braceletbook):
    body = client.get('/alpha/555/palette?n=1&hex_codes=ffffff').data.decode()
    assert '.k-a{fill:#fff}' in body
    assert 'href="/alpha/555?hex_codes=ffffff"' in body
    assert 'const BASE_PATH = "/alpha/555";' in body


def test_unknown_number_checks_both_kinds(client, braceletbook):
    response = client.get('/alpha/777')
    assert response.headers['Location'] == '/?error=not_found&design=777'
    assert any('/patterns/normal/777/' in url for url, _ in braceletbook)
    assert any('/patterns/alpha/777/' in url for url, _ in braceletbook)
    assert b'normal or alpha pattern' in client.get(response.headers['Location']).data
