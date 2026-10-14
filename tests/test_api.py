import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.main import app, analysis, connect
from literature_mining.analysis import gap_metrics

client = TestClient(app)


def test_readiness_and_real_counts():
    assert client.get('/api/health').json()['status'] == 'ready'
    o = client.get('/api/overview').json()
    assert o['total_papers'] == 10000
    assert o['title_only_papers'] == 2421
    assert o['abstract_papers'] == 7579
    assert len(o['years']) == 8
    assert sum(t['paper_count'] for t in o['top_topics']) == o['model_eligible']


def test_search_year_source_topic_and_pagination():
    r = client.get('/api/papers', params={'q': 'neural', 'year': 2020, 'source': 'title-and-abstract', 'sort': 'relevance'})
    assert r.status_code == 200 and r.json()['total'] > 0
    for p in r.json()['items']:
        assert p['publication_year'] == 2020 and p['abstract']
        assert 'neural' in (p['title'] + p['abstract'] + ' '.join(p['keywords'])).lower()
    r = client.get('/api/papers', params={'topic': 0, 'model': 'nmf'})
    assert all(p['nmf_topic'] == 0 for p in r.json()['items'])
    a = client.get('/api/papers?page=1').json()['items']
    b = client.get('/api/papers?page=2').json()['items']
    assert {p['paper_id'] for p in a}.isdisjoint({p['paper_id'] for p in b})
    assert client.get('/api/papers?q=zzzxxyynonexistent').json()['total'] == 0
    assert client.get('/api/papers', params={'q': '" OR 1=1 --'}).status_code == 200


def test_api_invalid_requests():
    for path in ['/api/topics/100', '/api/papers/W000000000', '/api/network/unknown', '/api/gaps/unknown']:
        assert client.get(path).status_code == 404
    for path in ['/api/papers?year=2010', '/api/topics?model=bad', '/api/trends?start=2025&end=2018', '/api/network?min_weight=-1']:
        assert client.get(path).status_code == 422


def test_topics_evaluation_and_temporal_outputs_match_artifacts():
    a = analysis()
    for model in ['lda', 'nmf']:
        api = client.get(f'/api/topics?model={model}').json()
        assert api == a['models'][model]
        detail = client.get(f'/api/topics/0?model={model}').json()
        assert len(detail['papers']) == 6
        years = client.get(f'/api/trends?model={model}').json()['years']
        for year in years:
            assert sum(t['prevalence'] for t in year['topics']) == pytest.approx(1)
        assert client.get('/api/evaluation').json()['models'][model] == a['models'][model]['metrics']


def test_network_real_edges_and_evidence():
    n = client.get('/api/network').json()
    assert n['nodes'] and n['edges']
    assert all(e['weight'] >= 20 and 0 <= e['jaccard'] <= 1 for e in n['edges'])
    term = client.get('/api/network/' + n['nodes'][0]['id']).json()
    assert term['papers']
    assert all(p['paper_id'].startswith('https://openalex.org/W') for p in term['papers'])
    assert client.get('/api/network?min_weight=10000000').json()['edges'] == []
    bundle = joblib.load(ROOT / 'artifacts/models.joblib')
    features = joblib.load(ROOT / 'artifacts/features.joblib')
    counts = features['count_matrix']
    labels = {node['id']: node['label'] for node in n['nodes']}
    vocabulary = bundle['counts'].vocabulary_
    for edge in n['edges']:
        left = counts[:, vocabulary[labels[edge['source']]]].toarray().ravel() > 0
        right = counts[:, vocabulary[labels[edge['target']]]].toarray().ravel() > 0
        assert int((left & right).sum()) == edge['weight']
        assert (left & right).sum() / (left | right).sum() == pytest.approx(edge['jaccard'])


def test_gap_evidence_and_statistics_are_actual_records():
    candidates = client.get('/api/gaps').json()['items']
    assert candidates
    features = joblib.load(ROOT / 'artifacts/features.joblib')
    dist = features['distributions']['nmf']
    ids = features['paper_ids']
    index = {pid: i for i, pid in enumerate(ids)}
    db = connect()
    abstracts = {r['paper_id']: bool(r['abstract']) for r in db.execute('SELECT paper_id,abstract FROM papers')}
    db.close()
    eligible = np.array([abstracts[pid] for pid in ids]) & (dist.sum(axis=1) > 0)
    for g in candidates:
        detail = client.get('/api/gaps/' + g['id']).json()
        a, b = dist[:, g['topic_a']] >= g['threshold'], dist[:, g['topic_b']] >= g['threshold']
        assert int((a & b & eligible).sum()) == g['observed']
        assert g['expected_independence'] == pytest.approx(g['a_count'] * g['b_count'] / g['eligible_count'], abs=0.01)
        expected_score = gap_metrics(g['eligible_count'], g['a_count'], g['b_count'], g['observed'])['score'] * np.sqrt(g['semantic_affinity'])
        assert g['score'] == pytest.approx(expected_score, abs=0.0001)
        assert detail['support_a'] and detail['support_b']
        for p in detail['counter_evidence']:
            assert a[index[p['paper_id']]] and b[index[p['paper_id']]] and eligible[index[p['paper_id']]]
        assert all(p['paper_id'] in index for group in ['support_a', 'support_b', 'counter_evidence'] for p in detail[group])


def test_models_reload_and_transform():
    bundle = joblib.load(ROOT / 'artifacts/models.joblib')
    x = bundle['counts'].transform(['neural network classification deep learning'])
    xt = bundle['tfidf'].transform(x)
    for name, matrix in [('nmf', xt), ('lda', x)]:
        weights = bundle['models'][name].transform(matrix)
        assert weights.shape == (1, 10) and np.isfinite(weights).all()
        assert (weights >= 0).all()
