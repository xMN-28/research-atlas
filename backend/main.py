import json
import re
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts'
if (Path(__file__).resolve().parent / 'runtime-data').exists():
    ART = Path(__file__).resolve().parent / 'runtime-data'
app = FastAPI(title='CEP 2 · Research Atlas', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                   allow_methods=['GET'], allow_headers=['*'])
Model = Literal['lda', 'nmf']


@lru_cache(maxsize=1)
def analysis():
    if not (ART / 'analysis.json').exists() or not (ART / 'research.sqlite').exists():
        raise HTTPException(503, 'Analysis artifacts missing. Run .venv\\Scripts\\python train.py first.')
    return json.loads((ART / 'analysis.json').read_text(encoding='utf-8'))


def connect():
    analysis()
    db = sqlite3.connect(f'{(ART / "research.sqlite").as_uri()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def paper(row):
    value = dict(row)
    value['keywords'] = json.loads(value['keywords'])
    value['abstract_missing'] = not bool(value['abstract'])
    value['openalex_url'] = value['paper_id']
    return value


def fetch_ids(ids):
    if not ids:
        return []
    with closing(connect()) as db:
        records = db.execute('SELECT * FROM papers WHERE paper_id IN (' + ','.join('?' for _ in ids) + ')', ids).fetchall()
    lookup = {r['paper_id']: paper(r) for r in records}
    return [lookup[i] for i in ids if i in lookup]


@app.get('/api/health')
def health():
    ready = (ART / 'analysis.json').exists() and (ART / 'research.sqlite').exists()
    return {'status': 'ready' if ready else 'untrained', 'models_retrained_on_request': False}


@app.get('/api/overview')
def overview():
    a = analysis()
    return {k: a[k] for k in ['generated_at', 'dataset_sha256', 'total_papers', 'abstract_papers',
        'title_only_papers', 'model_eligible', 'zero_feature_papers', 'vocabulary_size', 'training_seconds']} | {
        'topic_count': len(a['models']['nmf']['topics']), 'gap_count': len(a['gaps']),
        'years': a['trends']['nmf'], 'top_topics': a['models']['nmf']['topics'],
        'featured_gap': a['gaps'][0] if a['gaps'] else None, 'methodology': a['methodology']}


@app.get('/api/papers')
def papers(q: str = Query('', max_length=200), year: int | None = Query(None, ge=2018, le=2025),
           topic: int | None = Query(None, ge=0), model: Model = 'nmf',
           source: Literal['all', 'title-only', 'title-and-abstract'] = 'all',
           sort: Literal['citations', 'newest', 'relevance'] = 'citations',
           page: int = Query(1, ge=1, le=10000), limit: int = Query(20, ge=1, le=100)):
    if topic is not None and topic >= len(analysis()['models'][model]['topics']):
        raise HTTPException(422, 'Topic outside model range')
    clauses, params = [], []
    terms = re.findall(r'\w+', q, flags=re.UNICODE)
    search = bool(terms)
    join = ' JOIN papers_fts f ON p.paper_id=f.paper_id ' if search else ''
    if search:
        clauses.append('papers_fts MATCH ?')
        params.append(' AND '.join('"' + term + '"' for term in terms))
    if year:
        clauses.append('p.publication_year=?')
        params.append(year)
    if topic is not None:
        clauses.append(f'p.{model}_topic=?')
        params.append(topic)
    if source != 'all':
        clauses.append('p.text_source=?')
        params.append(source)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    order = 'bm25(papers_fts), p.paper_id' if sort == 'relevance' and search else ('p.publication_year DESC, p.citation_count DESC, p.paper_id' if sort == 'newest' else 'p.citation_count DESC, p.paper_id')
    with closing(connect()) as db:
        total = db.execute('SELECT COUNT(*) FROM papers p ' + join + where, params).fetchone()[0]
        records = db.execute('SELECT p.* FROM papers p ' + join + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', params + [limit, (page - 1) * limit]).fetchall()
    return {'total': total, 'page': page, 'limit': limit, 'items': [paper(r) for r in records]}


@app.get('/api/papers/{work_id}')
def paper_detail(work_id: str):
    records = fetch_ids(['https://openalex.org/' + work_id])
    if not records:
        raise HTTPException(404, 'Paper not found')
    return records[0]


@app.get('/api/topics')
def topics(model: Model = 'nmf'):
    return analysis()['models'][model]


@app.get('/api/topics/{topic_id}')
def topic_detail(topic_id: int, model: Model = 'nmf'):
    items = analysis()['models'][model]['topics']
    if not 0 <= topic_id < len(items):
        raise HTTPException(404, 'Topic not found')
    item = items[topic_id]
    return item | {'papers': fetch_ids(item['representative_ids'])}


@app.get('/api/trends')
def trends(model: Model = 'nmf', start: int = Query(2018, ge=2018, le=2025),
           end: int = Query(2025, ge=2018, le=2025)):
    if start > end:
        raise HTTPException(422, 'Start year must not exceed end year')
    a = analysis()
    return {'years': [row for row in a['trends'][model] if start <= row['year'] <= end],
            'topics': a['models'][model]['topics'], 'methodology': a['methodology']['trends']}


@app.get('/api/network')
def network(min_weight: int = Query(20, ge=1), min_jaccard: float = Query(0, ge=0, le=1)):
    n = analysis()['network']
    edges = [e for e in n['edges'] if e['weight'] >= min_weight and e['jaccard'] >= min_jaccard]
    return {'nodes': n['nodes'], 'edges': edges, 'method': n['method'], 'all_edges_count': n['all_edges_count']}


@app.get('/api/network/{term_id}')
def term_detail(term_id: str):
    n = analysis()['network']
    node = next((node for node in n['nodes'] if node['id'] == term_id), None)
    if not node:
        raise HTTPException(404, 'Term not found')
    return {'node': node, 'connections': [e for e in n['edges'] if term_id in (e['source'], e['target'])],
            'papers': fetch_ids(n['evidence'][term_id])}


@app.get('/api/gaps')
def gaps(topic: int | None = Query(None, ge=0), max_observed: int | None = Query(None, ge=0)):
    items = analysis()['gaps']
    return {'items': [g for g in items if (topic is None or topic in (g['topic_a'], g['topic_b']))
            and (max_observed is None or g['observed'] <= max_observed)],
            'methodology': analysis()['methodology']['gaps']}


@app.get('/api/gaps/{gap_id}')
def gap_detail(gap_id: str):
    gap = next((g for g in analysis()['gaps'] if g['id'] == gap_id), None)
    if not gap:
        raise HTTPException(404, 'Candidate not found')
    return gap | {'support_a': fetch_ids(gap['support_a_ids']), 'support_b': fetch_ids(gap['support_b_ids']),
                  'counter_evidence': fetch_ids(gap['counter_evidence_ids'])}


@app.get('/api/evaluation')
def evaluation():
    a = analysis()
    return {'models': {n: v['metrics'] for n, v in a['models'].items()},
            'methodology': a['methodology'], 'generated_at': a['generated_at'],
            'dataset_sha256': a['dataset_sha256']}
