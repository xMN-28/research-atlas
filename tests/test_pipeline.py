import pytest
from literature_mining import pipeline as p


def test_abstract_reconstructs_repeated_words_and_missing():
    assert p.abstract({'learning': [1, 3], 'Machine': [0], 'supports': [2]}) == 'Machine learning supports learning'
    assert p.abstract(None) == ''
    with pytest.raises(ValueError):
        p.abstract({'a': [0], 'b': [0]})


def test_clean_preserves_missing_and_normalizes_doi():
    row = p.clean({'id': 'https://openalex.org/W1', 'title': '  Test\n paper ',
                   'doi': 'HTTP://DX.DOI.ORG/10.123/ABC', 'publication_year': 2018})
    assert row['doi'] == 'https://doi.org/10.123/abc'
    assert row['title'] == 'Test paper'
    assert row['abstract_missing'] is True
    assert row['citation_count'] == ''
    assert row['keywords'] == '[]'


def test_cached_page_reused_without_network(tmp_path):
    class Fake:
        calls = 0
        def get(self, params):
            self.calls += 1
            return {'meta': {'count': 1}, 'results': [{'id': 'W1'}]}
    client = Fake()
    path = tmp_path / 'page.json'
    first = p.cached(client, path, {'page': 1})
    assert p.cached(client, path, {'page': 1}) == first
    assert client.calls == 1
    with pytest.raises(RuntimeError):
        p.cached(client, path, {'page': 2})


def test_rate_limit_then_success(monkeypatch):
    monkeypatch.setattr(p, 'dotenv_values', lambda _: {'OPENALEX_API_KEY': 'test'})
    sleeps = []
    monkeypatch.setattr(p.time, 'sleep', sleeps.append)
    class Reply:
        def __init__(self, code):
            self.status_code = code
            self.headers = {'Retry-After': '3'}
        def json(self):
            return {'meta': {}, 'results': []}
    replies = iter([Reply(429), Reply(503), Reply(200)])
    client = p.Client(retries=3)
    monkeypatch.setattr(client.session, 'get', lambda *a, **kw: next(replies))
    assert client.get({}) == {'meta': {}, 'results': []}
    assert sleeps[1] >= 3


def test_auth_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(p, 'dotenv_values', lambda _: {'OPENALEX_API_KEY': 'test-secret'})
    monkeypatch.setattr(p.time, 'sleep', lambda _: None)
    class Reply:
        status_code = 401
    client = p.Client()
    monkeypatch.setattr(client.session, 'get', lambda *a, **kw: Reply())
    with pytest.raises(RuntimeError, match='HTTP 401') as error:
        client.get({})
    assert 'test-secret' not in str(error.value)
