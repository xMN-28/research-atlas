"""Local, reproducible modelling and evidence generation. No external AI services."""
import argparse
import hashlib
import json
import math
import re
import sqlite3
import time
from itertools import combinations
from pathlib import Path

import joblib
import networkx as nx
import numpy as np
import pandas as pd
import spacy
from spacy.lang.es.stop_words import STOP_WORDS as ES_STOP
from spacy.lang.id.stop_words import STOP_WORDS as ID_STOP
from spacy.lang.pt.stop_words import STOP_WORDS as PT_STOP
from spacy.lang.fr.stop_words import STOP_WORDS as FR_STOP
from spacy.lang.de.stop_words import STOP_WORDS as DE_STOP
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits

from .pipeline import ROOT, now, save_json

ART = ROOT / 'artifacts'
EXTRA_STOP = {'paper', 'propose', 'proposed', 'approach', 'method', 'methods', 'result', 'results',
              'using', 'based', 'study', 'show', 'shown', 'et', 'al', 'however', 'new', 'also',
              'abstract', 'copyright', 'elsevier', 'rights', 'reserved', 'conference', 'ieee'}


def normalize_documents(titles, abstracts):
    nlp = spacy.blank('en')  # tokenizer only; no downloaded language model required
    stop = set(ENGLISH_STOP_WORDS) | EXTRA_STOP | nlp.Defaults.stop_words | ES_STOP | ID_STOP | PT_STOP | FR_STOP | DE_STOP
    docs = (str(t) + '. ' + str(a) for t, a in zip(titles, abstracts))
    return [' '.join(token.lower_ for token in doc if token.is_alpha and len(token.text) > 2
                     and token.lower_ not in stop) for doc in nlp.pipe(docs, batch_size=128)]


def normalize_weights(weights):
    sums = weights.sum(axis=1, keepdims=True)
    return np.divide(weights, sums, out=np.zeros_like(weights), where=sums > 0)


def npmi(binary, indices):
    n = binary.shape[0]
    scores = []
    for left, right in combinations(indices, 2):
        pa = binary[:, left].sum() / n
        pb = binary[:, right].sum() / n
        pab = binary[:, left].multiply(binary[:, right]).sum() / n
        scores.append(-1.0 if pab == 0 else (math.log(pab / (pa * pb)) / -math.log(pab) if pab < 1 else 0.0))
    return float(np.mean(scores))


def stability(a, b):
    sim = cosine_similarity(a, b)
    row, col = linear_sum_assignment(-sim)
    return float(sim[row, col].mean())


def gap_metrics(n, a, b, intersection):
    expected = a * b / n
    deficit = max(0, 1 - intersection / expected) if expected else 0
    balance = 2 * min(a, b) / (a + b) if a + b else 0
    score = deficit * balance * math.log1p(min(a, b)) / math.log1p(n)
    return {'expected_independence': round(expected, 2), 'observed': int(intersection),
            'deficit_fraction': round(deficit, 4), 'balance': round(balance, 4),
            'score': round(score, 4)}


def train(topics=10, max_features=6000, allow_new_corpus=False):
    ART.mkdir(exist_ok=True)
    started = time.perf_counter()
    df = pd.read_csv(ROOT / 'data/research_papers.csv', keep_default_na=False)
    if not allow_new_corpus and (len(df) != 10000 or df.paper_id.nunique() != 10000):
        raise ValueError('Expected the complete unique 10,000-record Phase 1 dataset')
    if df.paper_id.nunique() != len(df) or len(df) < 100:
        raise ValueError('Corpus must contain unique records and at least 100 papers')
    sampling = json.loads((ROOT / 'data/metadata/sampling.json').read_text(encoding='utf-8'))
    if set(df.publication_year) != set(range(2018, 2026)):
        raise ValueError('This platform currently supports complete 2018–2025 collections')
    for year, count in df.groupby('publication_year').size().items():
        if sampling['years'][str(year)]['selected'] != int(count):
            raise ValueError('Yearly sampling metadata does not match the CSV')
    checksum = hashlib.sha256((ROOT / 'data/research_papers.csv').read_bytes()).hexdigest()
    if sampling['csv_sha256'] != checksum:
        raise ValueError('Dataset checksum does not match Phase 1 provenance')
    print(f'Preprocessing {len(df):,} title + available-abstract records with spaCy tokenizer', flush=True)
    texts = normalize_documents(df.title, df.abstract)
    counts = CountVectorizer(ngram_range=(1, 2), min_df=12, max_df=0.65,
                            max_features=max_features, dtype=np.float64)
    x = counts.fit_transform(texts)
    tfidf = TfidfTransformer(sublinear_tf=True)
    xt = tfidf.fit_transform(x)
    features = counts.get_feature_names_out()
    active = np.asarray(x.sum(axis=1)).ravel() > 0
    binary = x.copy()
    binary.data[:] = 1
    train_idx, test_idx = train_test_split(np.flatnonzero(active), test_size=0.2,
                                         random_state=42, stratify=df.publication_year[active])
    models, output, distributions = {}, {}, {}
    for name in ('nmf', 'lda'):
        print(f'Training and evaluating {name.upper()} ({topics} topics, {len(features)} features)', flush=True)
        model_start = time.perf_counter()
        def make(seed):
            if name == 'lda':
                return LatentDirichletAllocation(n_components=topics, max_iter=12,
                    learning_method='batch', random_state=seed, n_jobs=1, evaluate_every=-1)
            return NMF(n_components=topics, init='nndsvdar', random_state=seed,
                       max_iter=450, tol=0.0005)
        matrix = x if name == 'lda' else xt
        # Evaluation models see only training documents; coherence evaluated on held-out documents.
        evaluation_model = make(42).fit(matrix[train_idx])
        rerun = make(73).fit(matrix[train_idx])
        top_eval = [np.argsort(c)[-10:][::-1] for c in evaluation_model.components_]
        coherence = [npmi(binary[test_idx], indices) for indices in top_eval]
        unique = len(set(int(i) for indices in top_eval for i in indices)) / (topics * 10)
        metrics = {'coherence_npmi': float(np.mean(coherence)), 'topic_diversity': unique,
                   'seed_stability_cosine': stability(evaluation_model.components_, rerun.components_),
                   'interpretability_proxy': float(np.mean([len(set(features[i].split()[0] for i in ix)) / 10 for ix in top_eval])),
                   'heldout_documents': len(test_idx), 'training_documents': len(train_idx),
                   'evaluation_iterations': int(evaluation_model.n_iter_)}
        if name == 'lda':
            metrics['heldout_perplexity'] = float(evaluation_model.perplexity(x[test_idx]))
        else:
            h = evaluation_model.transform(xt[test_idx])
            # Squared reconstruction error without densifying document-feature matrices.
            error2 = xt[test_idx].multiply(xt[test_idx]).sum() - 2 * np.sum(h * (xt[test_idx] @ evaluation_model.components_.T))
            error2 += np.sum((h @ (evaluation_model.components_ @ evaluation_model.components_.T)) * h)
            metrics['heldout_rmse'] = float(np.sqrt(max(0, error2) / (len(test_idx) * len(features))))
        model = make(42)
        weights = model.fit_transform(matrix[active])
        dist = np.zeros((len(df), topics))
        dist[active] = normalize_weights(weights)
        distributions[name] = dist
        models[name] = model
        top = [np.argsort(c)[-12:][::-1] for c in model.components_]
        topic_rows = []
        for k, indices in enumerate(top):
            # Labels generated directly from learned components, not hand-authored findings.
            labels = []
            for ix in indices:
                term = features[ix]
                roots = lambda phrase: {w[:-1] if w.endswith('s') and len(w) > 4 else w for w in phrase.split()}
                if not any(roots(term) <= roots(label) or roots(label) <= roots(term) for label in labels):
                    labels.append(term)
                if len(labels) == 3:
                    break
            assigned = (dist.argmax(axis=1) == k) & active
            representatives = np.argsort(dist[:, k])[::-1][:6]
            topic_rows.append({'id': k, 'label': ' · '.join(labels),
                'words': [{'term': features[i], 'weight': float(model.components_[k, i])} for i in indices],
                'paper_count': int(assigned.sum()), 'mean_weight': float(dist[active, k].mean()),
                'representative_ids': df.paper_id.iloc[representatives].tolist(),
                'coherence_npmi_full': npmi(binary[active], indices[:10])})
        metrics['fit_seconds'] = round(time.perf_counter() - model_start, 2)
        output[name] = {'topics': topic_rows, 'metrics': metrics}
    print('Computing annual topic prevalence and text-coverage sensitivity', flush=True)
    trends = {}
    for name, dist in distributions.items():
        trends[name] = []
        for year in range(2018, 2026):
            mask = (df.publication_year.to_numpy() == year) & active
            full = mask & (df.abstract.to_numpy() != '')
            original = df.publication_year.to_numpy() == year
            row = {'year': year, 'sample_count': int(original.sum()), 'model_eligible_count': int(mask.sum()),
                   'abstract_count': int((original & (df.abstract.to_numpy() != '')).sum()), 'corpus_count': sampling['years'][str(year)]['corpus_count'],
                   'topics': []}
            for k in range(topics):
                values = dist[mask, k]
                mean = values.mean()
                se = values.std(ddof=1) / math.sqrt(len(values))
                row['topics'].append({'id': k, 'prevalence': float(mean),
                    'lower': float(max(0, mean - 1.96 * se)), 'upper': float(min(1, mean + 1.96 * se)),
                    'abstract_only_prevalence': float(dist[full, k].mean()),
                    'dominant_count': int((dist[mask].argmax(axis=1) == k).sum())})
            trends[name].append(row)
    print('Extracting weighted technical-term co-occurrence network', flush=True)
    importance = np.asarray(xt.sum(axis=0)).ravel()
    # Scientific terms are statistical candidates, not ontology-verified entities.
    term_indices = sorted(np.argsort(importance)[-65:], key=lambda i: features[i])
    term_binary = binary[:, term_indices].astype(np.int64)
    co = (term_binary.T @ term_binary).toarray()
    graph = nx.Graph()
    term_evidence = {}
    for local, global_ix in enumerate(term_indices):
        key = f't{local}'
        support = term_binary[:, local].toarray().ravel() > 0
        ordered = np.argsort(xt[:, global_ix].toarray().ravel())[::-1]
        graph.add_node(key, label=features[global_ix], count=int(support.sum()), importance=float(importance[global_ix]))
        term_evidence[key] = df.paper_id.iloc[[i for i in ordered if support[i]][:12]].tolist()
    for a, b in combinations(range(len(term_indices)), 2):
        if co[a, b] >= 20:
            jaccard = co[a, b] / (co[a, a] + co[b, b] - co[a, b])
            graph.add_edge(f't{a}', f't{b}', weight=int(co[a, b]), jaccard=float(jaccard))
    # Retain strongest edges for legibility, without inventing connections.
    edges = sorted(graph.edges(data=True), key=lambda edge: edge[2]['jaccard'], reverse=True)[:200]
    display_graph = nx.Graph()
    display_graph.add_nodes_from(graph.nodes(data=True))
    display_graph.add_edges_from(edges)
    positions = nx.spring_layout(display_graph, seed=42, iterations=80, weight='jaccard')
    centrality = nx.degree_centrality(graph)
    network = {'nodes': [{'id': n, **attrs, 'centrality': centrality[n],
                          'x': float(positions[n][0] * 450), 'y': float(positions[n][1] * 340)} for n, attrs in graph.nodes(data=True)],
               'edges': [{'source': a, 'target': b, **attrs} for a, b, attrs in edges],
               'all_edges_count': graph.number_of_edges(), 'evidence': term_evidence,
               'method': 'Top 65 features by corpus TF-IDF mass; document-level binary unigram/bigram co-occurrence; minimum 20 shared papers; strongest 200 Jaccard edges displayed.'}
    print('Ranking intersection hypotheses with paper-level evidence', flush=True)
    dist = distributions['nmf']
    eligible = active & (df.abstract.to_numpy() != '')
    threshold = 0.15
    membership = dist >= threshold
    topic_affinity = cosine_similarity(models['nmf'].components_)
    gaps = []
    for a, b in combinations(range(topics), 2):
        ma, mb = membership[:, a] & eligible, membership[:, b] & eligible
        intersection = ma & mb
        if min(ma.sum(), mb.sum()) < 100:
            continue
        metrics = gap_metrics(int(eligible.sum()), int(ma.sum()), int(mb.sum()), int(intersection.sum()))
        if metrics['deficit_fraction'] <= 0:
            continue
        affinity = float(topic_affinity[a, b])
        base_score = metrics['score']
        metrics['score'] = round(base_score * math.sqrt(max(0, affinity)), 4)
        def evidence(mask, score, limit=5):
            return df.paper_id.iloc[[i for i in np.argsort(score)[::-1] if mask[i]][:limit]].tolist()
        yearly = []
        for year in range(2018, 2026):
            m = df.publication_year.to_numpy() == year
            yearly.append({'year': year, 'a_count': int((ma & m).sum()), 'b_count': int((mb & m).sum()),
                           'intersection_count': int((intersection & m).sum())})
        title_membership = membership & active[:, None]
        sensitivity = int((title_membership[:, a] & title_membership[:, b]).sum())
        threshold_sensitivity = {str(t): int(((dist[:, a] >= t) & (dist[:, b] >= t) & eligible).sum()) for t in [0.1, 0.15, 0.2]}
        gaps.append({'id': f'nmf-{a}-{b}', 'topic_a': a, 'topic_b': b,
            'label_a': output['nmf']['topics'][a]['label'], 'label_b': output['nmf']['topics'][b]['label'],
            **metrics, 'base_score': base_score, 'semantic_affinity': affinity,
            'a_count': int(ma.sum()), 'b_count': int(mb.sum()), 'eligible_count': int(eligible.sum()),
            'threshold': threshold, 'intersection_with_title_only': sensitivity,
            'threshold_sensitivity': threshold_sensitivity, 'yearly': yearly,
            'support_a_ids': evidence(ma & ~mb, dist[:, a]),
            'support_b_ids': evidence(mb & ~ma, dist[:, b]),
            'counter_evidence_ids': evidence(intersection, np.minimum(dist[:, a], dist[:, b]), 8),
            'status': 'Review hypothesis',
            'explanation': 'Both learned themes have substantial separate literature. Their observed shared membership is below an independence baseline in abstract-bearing records. Ranking also considers cosine similarity of their learned term vectors to reduce the priority of unrelated themes. Existing intersection papers are counter-evidence to novelty. Independence is a heuristic; normalized mixtures, model boundaries, language, text availability or natural specialization can explain the deficit. Read the evidence and search external literature before claiming a validated gap.'})
    gaps.sort(key=lambda g: g['score'], reverse=True)
    for i, gap in enumerate(gaps):
        gap['rank'] = i + 1
    print('Persisting fitted models, sparse features, SQLite and analysis artifacts', flush=True)
    joblib.dump({'counts': counts, 'tfidf': tfidf, 'models': models,
                 'config': {'topics': topics, 'seed': 42, 'features': len(features)}}, ART / 'models.joblib', compress=3)
    joblib.dump({'count_matrix': x, 'tfidf_matrix': xt, 'distributions': distributions,
                 'paper_ids': df.paper_id.tolist(), 'train_indices': train_idx, 'test_indices': test_idx}, ART / 'features.joblib', compress=3)
    df['text_source'] = np.where(df.abstract == '', 'title-only', 'title-and-abstract')
    df['model_eligible'] = active.astype(int)
    for name, dist in distributions.items():
        df[f'{name}_topic'] = np.where(active, dist.argmax(axis=1), -1)
        df[f'{name}_confidence'] = dist.max(axis=1)
    db_tmp = ART / 'research.tmp.sqlite'
    with sqlite3.connect(db_tmp) as db:
        df.to_sql('papers', db, if_exists='replace', index=False)
        db.execute('CREATE INDEX IF NOT EXISTS papers_id ON papers(paper_id)')
        db.execute('CREATE INDEX IF NOT EXISTS papers_year ON papers(publication_year)')
        db.execute('CREATE INDEX IF NOT EXISTS papers_nmf ON papers(nmf_topic)')
        db.execute('CREATE INDEX IF NOT EXISTS papers_lda ON papers(lda_topic)')
        db.execute('DROP TABLE IF EXISTS papers_fts')
        db.execute('CREATE VIRTUAL TABLE papers_fts USING fts5(paper_id UNINDEXED, title, abstract, keywords)')
        db.execute('INSERT INTO papers_fts SELECT paper_id,title,abstract,keywords FROM papers')
        db.commit()
    db.close()  # sqlite context managers commit but do not close; Windows requires closure before rename.
    db_tmp.replace(ART / 'research.sqlite')
    checksum = hashlib.sha256((ROOT / 'data/research_papers.csv').read_bytes()).hexdigest()
    analysis = {'generated_at': now(), 'dataset_sha256': checksum, 'total_papers': len(df),
        'abstract_papers': int((df.abstract != '').sum()), 'title_only_papers': int((df.abstract == '').sum()),
        'model_eligible': int(active.sum()), 'zero_feature_papers': int((~active).sum()),
        'vocabulary_size': len(features), 'models': output, 'trends': trends, 'network': network,
        'gaps': gaps, 'sampling': sampling,
        'methodology': {'preprocessing': 'spaCy tokenizer, lowercase alphabetic tokens, English plus Spanish/Indonesian/Portuguese/French/German function-word stoplists and corpus boilerplate stopwords. All records retained; no language translation, lemmatization or silent abstract imputation. Language-specific content words can still form multilingual topics.',
            'features': 'Shared 1–2 gram vocabulary; min_df=12, max_df=0.65, max_features=' + str(max_features) + '. NMF: sublinear TF-IDF; LDA: raw counts.',
            'coherence': 'Mean document-level NPMI over all 45 pairs of top 10 terms per topic, measured on held-out 20% documents. Unseen pairs score -1. Higher is better; range [-1,1]. Vocabulary is corpus-wide, so this is descriptive held-out topic evaluation rather than a leakage-free prediction benchmark.',
            'diversity': 'Distinct top-10 terms / (10 × topic count), evaluated on training-fit topics.',
            'stability': 'Two seeds (42 and 73) on the same 80% training subset, optimally matched by Hungarian assignment of cosine similarity. Seed stability only, not bootstrap robustness.',
            'interpretability': 'Lexical distinctiveness proxy: mean fraction of distinct leading words in top 10 terms. Not human-rated interpretability. Inspect labels and representative papers for qualitative assessment.',
            'trends': 'Mean normalized topic weight per year, using titles plus available abstracts. Shaded 95% normal intervals reflect sample variability, not model uncertainty. Abstract-only sensitivity also reported. Full-corpus counts are separate unsampled OpenAlex metadata; no volume extrapolation from equal quotas.',
            'gaps': 'NMF normalized memberships >=0.15 in abstract-bearing records; both margins >=100; observed below independence baseline. Score = deficit × balanced margins × log(1+smaller margin)/log(1+eligible corpus) × sqrt(cosine topic-term affinity). Similarity is a thematic relevance proxy, not proof of a meaningful intersection. Normalized mixtures impose compositional dependence, so the independence baseline is not a statistical significance test. Threshold and title-only sensitivities are saved. No validated novelty claim.'},
        'training_seconds': round(time.perf_counter() - started, 2)}
    save_json(ART / 'analysis.json', analysis)
    save_json(ART / 'evaluation.json', {'models': {name: value['metrics'] for name, value in output.items()},
               'methodology': analysis['methodology'], 'generated_at': analysis['generated_at'], 'dataset_sha256': checksum})
    print(json.dumps({'training_seconds': analysis['training_seconds'], 'gaps': len(gaps),
          'model_eligible': int(active.sum()), 'evaluation': {n: o['metrics'] for n, o in output.items()}}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topics', type=int, default=10)
    parser.add_argument('--max-features', type=int, default=6000)
    parser.add_argument('--allow-new-corpus', action='store_true', help='Allow a different-sized 2018–2025 corpus with matching Phase 1 sampling metadata')
    args = parser.parse_args()
    if not 2 <= args.topics <= 30:
        parser.error('Topics must be between 2 and 30')
    with threadpool_limits(limits=2):
        train(args.topics, args.max_features, args.allow_new_corpus)


if __name__ == '__main__':
    main()
