# Scientific Literature Mining and Research Gap Discovery — CEP 2

Phase 1 only: local Windows dataset collection, cleaning and validation. No models or web application are implemented.

## Setup (PowerShell, Python 3.12)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and replace the placeholder with your OpenAlex key. If `.env` already contains your key, skip the copy command. The program reads this file directly and sends authentication in a bearer header. `.env` is ignored by Git. Never commit or paste it into logs.

```powershell
.venv\Scripts\python collect.py collect
.venv\Scripts\python collect.py validate
.venv\Scripts\python -m pytest -q
```

Activation is unnecessary, so PowerShell execution-policy changes are unnecessary. Run from the project directory; output paths are anchored to the project even if launched elsewhere. A connection to OpenAlex is required for uncached pages.

## Dataset selection

The live-verified filter is `primary_topic.subfield.id:1702,publication_year:2018,type:article|preprint`, with the year changed for each cohort. Subfield 1702 is verified against the subfields endpoint as **Artificial Intelligence**. This deliberately selects papers whose **primary** topic belongs to AI; it does not cover every paper mentioning AI/ML or every secondary AI topic. Article and preprint records are included, including conference papers classified as articles by OpenAlex. Reviews and other record types are excluded.

Each of 2018–2025 gets a seeded random candidate sample of 1,500 records (`seed=42+year`), fetched in pages of 200. Candidates are shuffled locally with the same seed and the first 1,250 eligible unique papers are retained: 10,000 total. Sampling does not rank by citation count or require an abstract. OpenAlex random samples use numbered pagination; cursor pagination is implemented separately because the API does not support cursors on sampled queries.

Optional cursor collection:

```powershell
.venv\Scripts\python collect.py collect --mode cursor
```

Cursor mode starts at `*` and follows `meta.next_cursor`, sorted by publication date. It creates a date-ordered candidate subset and is **not representative random sampling**; use the default sample mode for the main dataset. Both modes write the same final CSV location. Different modes/seeds/sample sizes have isolated raw caches. Larger candidate pools can be requested with `--candidates 2000` if duplicate removal prevents meeting a quota (maximum 10,000). The collector fails rather than silently publishing fewer papers.

## Files and reproducibility

```text
collect.py                       command-line entry point
src/literature_mining/pipeline.py collection, cleaning, validation
tests/                           focused reliability tests
data/research_papers.csv          final UTF-8 BOM CSV, Excel compatible
data/raw/<config-hash>/           immutable JSON response pages and corpus counts
data/metadata/sampling.json       filters, seeds, cohort sizes, rejection counts
data/metadata/validation.json     dataset statistics and checksum
```

Raw snapshots retain inverted indexes and exact selected API fields, request parameters, and UTC acquisition timestamps. They omit authentication. The configuration hash separates cache sets. Completed pages are written atomically; rerunning the same command reuses them and fetches only missing pages. An interrupted final CSV write cannot replace the previous complete CSV. Processing rebuilds from cached pages and is deterministic for those snapshots; seeds alone cannot freeze a changing live OpenAlex database. Keep the raw directory and metadata together when archiving results. This repository includes the original dataset, raw snapshots and metadata for reproducibility. To obtain a fresh snapshot, archive the existing raw run directory first and rerun.

The client spaces requests by 0.25 seconds, uses connect/read timeouts, retries network failures, malformed JSON and HTTP 429/500/502/503/504 up to eight attempts with exponential backoff and jitter, and honors `Retry-After`. Other HTTP failures stop promptly without logging response bodies or credentials. If the daily API budget is exhausted, rerun after reset; completed pages survive.

## Cleaning and schema

Required columns: `paper_id`, `title`, `abstract`, `publication_year`, `keywords`, `research_topic`, `doi`, `citation_count`. Additional columns: `research_topic_id`, `subfield_id`, `work_type`, `abstract_missing`, `keywords_missing`.

Abstracts are reconstructed by sorting inverted-index token positions, preserving repeated tokens and original capitalization. Whitespace is normalized in textual fields. Keywords are a JSON array inside a properly quoted CSV cell, preserving keyword boundaries; no inferred keywords are invented. DOI strings are normalized to lowercase `https://doi.org/...`. Duplicate OpenAlex IDs and nonempty normalized DOIs are removed globally. Identical titles alone are not a reliable duplicate key and are retained; preprint/published versions with distinct IDs and DOIs may remain.

Missing ID/title records are excluded. Missing abstracts, DOI, topic and citation values remain empty; missing keyword lists are `[]`. Missing abstract/keyword flags make exclusions for later text modelling explicit. Missing citation values are not converted to zero. Validation checks exact year quotas, schema, ID and DOI uniqueness, AI subfield membership, DOI syntax, nonnegative citation values, keyword JSON and missingness flags, then prints year counts, all column missing-value counts and total unique papers.

## Temporal-analysis caveats

`sampling.json` preserves the full filtered OpenAlex corpus count per year using a separate **unsampled** query. Do not use the equal 1,250-paper sample counts to infer publication growth. Nominal selected fractions are recorded for context, not guaranteed inverse-probability weights after cleaning/DOI deduplication. Use corpus counts for indexed publication volume and sample topic proportions with uncertainty for composition. Report abstract missingness per year when analyzing text; using only available abstracts can introduce bias. Citation counts are acquisition-time cumulative values and favor older papers. OpenAlex classifications and coverage change, and 2025 indexing may continue to backfill. These are counts of indexed records, not a census of all real-world AI research.

## Official references

- [OpenAlex subfields and valid primary-topic filters](https://help.openalex.org/data/subfields/)
- [Authentication and rate limits](https://help.openalex.org/api/authentication/)
- [Pagination](https://help.openalex.org/api/paging/)
- [Query parameters, including sample and seed](https://help.openalex.org/api/llm-quick-reference/)
- [Work attributes](https://help.openalex.org/data/works/attributes/)
- [Work types](https://help.openalex.org/data/work-types/)

OpenAlex metadata is openly available under CC0. This phase contains metadata and reconstructed abstracts rather than full-text PDFs.
