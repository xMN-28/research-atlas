"""Download immutable page snapshots; rebuild and validate a stratified CSV."""
import argparse
import csv
import hashlib
import json
import random
import time
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ['paper_id', 'title', 'abstract', 'publication_year', 'keywords',
          'research_topic', 'doi', 'citation_count', 'research_topic_id',
          'subfield_id', 'work_type', 'abstract_missing', 'keywords_missing']
SELECT = 'id,title,abstract_inverted_index,publication_year,keywords,primary_topic,doi,cited_by_count,type'


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def text(value):
    return ' '.join((value or '').split())


def abstract(index):
    if not index:
        return ''
    positions = {}
    for word, offsets in index.items():
        for offset in offsets:
            if not isinstance(offset, int) or offset < 0 or offset in positions:
                raise ValueError('Invalid abstract position')
            positions[offset] = word
    return text(' '.join(positions[pos] for pos in sorted(positions)))


def clean(work):
    topic = work.get('primary_topic') or {}
    doi = text(work.get('doi')).lower()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'http://dx.doi.org/', 'https://dx.doi.org/', 'doi:'):
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
            break
    body = abstract(work.get('abstract_inverted_index'))
    keywords = sorted({text(k.get('display_name')) for k in (work.get('keywords') or []) if text(k.get('display_name'))})
    return dict(zip(FIELDS, [work.get('id'), text(work.get('title')), body,
        work.get('publication_year'), json.dumps(keywords, ensure_ascii=False),
        text(topic.get('display_name')), 'https://doi.org/' + doi if doi else '',
        work.get('cited_by_count') if work.get('cited_by_count') is not None else '',
        topic.get('id') or '', (topic.get('subfield') or {}).get('id') or '',
        work.get('type') or '', not bool(body), not bool(keywords)]))


class Client:
    def __init__(self, retries=8, delay=0.25):
        key = dotenv_values(ROOT / '.env').get('OPENALEX_API_KEY')
        if not key or key == 'your_openalex_api_key':
            raise RuntimeError('Set OPENALEX_API_KEY in the project .env file')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer ' + key,
                                     'User-Agent': 'CEP2-LiteratureMining/1.0'})
        self.retries, self.delay = retries, delay

    def get(self, params, endpoint='works'):
        for attempt in range(self.retries):
            time.sleep(self.delay)
            try:
                response = self.session.get('https://api.openalex.org/' + endpoint,
                                            params=params, timeout=(15, 90))
            except requests.RequestException:
                response = None  # Never print exceptions containing authenticated URLs.
            if response is not None and response.status_code == 200:
                try:
                    result = response.json()
                    if endpoint == 'works' and ('meta' not in result or 'results' not in result):
                        raise ValueError('Invalid response envelope')
                    return result
                except ValueError:
                    pass
            elif response is not None and response.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f'OpenAlex HTTP {response.status_code}; check credentials and filters')
            if attempt == self.retries - 1:
                break
            wait = min(120, 2 ** attempt + random.random())
            retry_after = response.headers.get('Retry-After') if response is not None else None
            if retry_after:
                try:
                    wait = max(wait, float(retry_after))
                except ValueError:
                    try:
                        wait = max(wait, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        pass
            print(f'Transient API failure; retry {attempt + 1}/{self.retries} in {wait:.1f}s', flush=True)
            time.sleep(wait)
        raise RuntimeError('API retries exhausted. Rerun to resume cached pages.')


def cached(client, path, params):
    if path.exists():
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        if snapshot['parameters'] != params:
            raise RuntimeError('Cached parameters differ; use a new run directory')
        return snapshot['response'], snapshot['retrieved_at']
    result = client.get(params)
    stamp = now()
    save_json(path, {'retrieved_at': stamp, 'parameters': params, 'response': result})
    return result, stamp


def collect(args):
    config = {'years': list(range(2018, 2026)), 'target_per_year': args.per_year,
              'candidate_sample': args.candidates, 'seed': args.seed,
              'mode': args.mode, 'subfield': '1702', 'types': ['article', 'preprint'], 'version': 1}
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    raw = ROOT / 'data' / 'raw' / digest
    client = Client()
    subfield_path = raw / 'subfield.json'
    if not subfield_path.exists():
        save_json(subfield_path, client.get({}, 'subfields/1702'))
    if json.loads(subfield_path.read_text(encoding='utf-8'))['display_name'] != 'Artificial Intelligence':
        raise RuntimeError('Subfield identity verification failed')
    rows, ids, dois, yearly = [], set(), set(), {}
    for year in config['years']:
        filter_value = f'primary_topic.subfield.id:1702,publication_year:{year},type:article|preprint'
        count_response, count_date = cached(client, raw / str(year) / 'count.json',
                                           {'filter': filter_value, 'per_page': 1, 'select': 'id'})
        corpus_count = count_response['meta']['count']
        candidates, page, cursor = [], 1, '*'
        while len(candidates) < args.candidates:
            params = {'filter': filter_value, 'select': SELECT, 'per_page': 200}
            if args.mode == 'sample':
                params.update(sample=min(args.candidates, corpus_count), seed=args.seed + year, page=page)
            else:
                params.update(cursor=cursor, sort='publication_date:asc')
            response, stamp = cached(client, raw / str(year) / f'page_{page:04d}.json', params)
            batch = response['results']
            if not batch:
                break
            for work in batch:
                row = clean(work)
                if row['publication_year'] != year or row['subfield_id'] != 'https://openalex.org/subfields/1702':
                    raise RuntimeError('API returned a record outside the requested cohort')
                candidates.append(row)
            print(f'{year}: {len(candidates)}/{min(args.candidates, corpus_count)} candidates; page {page} saved', flush=True)
            page += 1
            if args.mode == 'cursor':
                next_cursor = response['meta'].get('next_cursor')
                if not next_cursor:
                    break
                if next_cursor == cursor:
                    raise RuntimeError('Cursor did not advance')
                cursor = next_cursor
            elif len(candidates) >= min(args.candidates, corpus_count):
                break
        candidates = candidates[:args.candidates]
        # Local seeded shuffle prevents page order from affecting selection.
        random.Random(args.seed + year).shuffle(candidates)
        kept, rejected = 0, Counter()
        for row in candidates:
            if not row['paper_id'] or not row['title']:
                rejected['missing_id_or_title'] += 1
                continue
            if row['paper_id'] in ids or (row['doi'] and row['doi'] in dois):
                rejected['duplicate_id_or_doi'] += 1
                continue
            if kept == args.per_year:
                continue
            rows.append(row)
            ids.add(row['paper_id'])
            if row['doi']:
                dois.add(row['doi'])
            kept += 1
        yearly[str(year)] = {'filter': filter_value, 'corpus_count': corpus_count,
            'count_retrieved_at': count_date, 'candidates_downloaded': len(candidates),
            'sample_seed': args.seed + year, 'selected': kept, 'rejections': dict(rejected),
            'nominal_selected_fraction': kept / corpus_count if corpus_count else 0}
        if kept != args.per_year:
            raise RuntimeError(f'{year}: only {kept} eligible papers; increase --candidates')
    out = ROOT / 'data' / 'research_papers.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.csv.tmp')
    with tmp.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(out)
    metadata = {'config': config, 'completed_at': now(), 'raw_directory': raw.relative_to(ROOT).as_posix(),
        'years': yearly, 'csv_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
        'sampling_caveat': 'Equal yearly quotas do not represent publication growth. Use corpus_count for volume trends. Missing text, primary-topic coverage and DOI deduplication can bias topic estimates. Cursor mode is a publication-date-ordered convenience subset, not a random corpus sample.'}
    save_json(ROOT / 'data' / 'metadata' / 'sampling.json', metadata)
    validate(out, args.per_year)


def validate(path, per_year=1250):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError('Unexpected CSV schema')
        rows = list(reader)
    years = Counter(int(r['publication_year']) for r in rows)
    unique = {r['paper_id'] for r in rows}
    dois = [r['doi'] for r in rows if r['doi']]
    if years != Counter({y: per_year for y in range(2018, 2026)}):
        raise ValueError(f'Unexpected year counts: {years}')
    if len(unique) != len(rows) or len(dois) != len(set(dois)):
        raise ValueError('Duplicate IDs or DOIs')
    for row in rows:
        if not row['paper_id'].startswith('https://openalex.org/W') or not row['title']:
            raise ValueError('Invalid ID/title')
        if row['subfield_id'] != 'https://openalex.org/subfields/1702':
            raise ValueError('Invalid subfield')
        if row['citation_count'] and int(row['citation_count']) < 0:
            raise ValueError('Negative citations')
        if row['doi'] and not row['doi'].startswith('https://doi.org/10.'):
            raise ValueError('Malformed DOI')
        keywords = json.loads(row['keywords'])
        if not isinstance(keywords, list) or any(not isinstance(k, str) for k in keywords):
            raise ValueError('Invalid keywords')
        if row['abstract_missing'] != str(not bool(row['abstract'])) or row['keywords_missing'] != str(not bool(keywords)):
            raise ValueError('Missingness flag mismatch')
    missing = {f: sum(not r[f] or (f == 'keywords' and r[f] == '[]') for r in rows) for f in FIELDS}
    report = {'total_papers': len(rows), 'unique_papers': len(unique), 'counts_by_year': dict(sorted(years.items())),
              'missing_values': missing, 'missing_abstracts_by_year': {y: sum(not r['abstract'] for r in rows if int(r['publication_year']) == y) for y in sorted(years)},
              'validated_at': now(), 'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    save_json(ROOT / 'data' / 'metadata' / 'validation.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'validate'])
    parser.add_argument('--per-year', type=int, default=1250)
    parser.add_argument('--candidates', type=int, default=1500)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--mode', choices=['sample', 'cursor'], default='sample')
    args = parser.parse_args()
    if not 0 < args.per_year <= args.candidates <= 10000:
        parser.error('Require 0 < per-year <= candidates <= 10000')
    try:
        if args.command == 'collect':
            collect(args)
        else:
            validate(ROOT / 'data' / 'research_papers.csv', args.per_year)
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Collection/validation stopped: {error}\n')


if __name__ == '__main__':
    main()
