# Local verification record

Tested on Windows with Python 3.12 and Node.js 24.13.0. Browsing reads local saved JSON/SQLite through the production Next.js proxy to FastAPI.

Verified:

- Original 10,000-paper checksum and sampling provenance match; every record remains in SQLite.
- Offline training completed; fitted NMF/LDA and vectorizers reload from joblib and transform new text.
- 17 Python tests pass: collection reliability, preprocessing/NPMI/stability/scoring logic, counts, FTS search, filters, pagination, error codes, API/artifact consistency, trends and graph evidence.
- Every hypothesis's observed intersection count is recalculated from saved NMF memberships; all supporting/counter-evidence IDs resolve to real records.
- Seven production pages render without captured browser JavaScript errors.
- Five browser suites pass: pages/charts/canvas; search/year/coverage/sort/modal/pagination/empty state; model/trend/graph/gap controls; export/themes/mobile; simulated 503/retry recovery.
- Next.js production build and TypeScript checks pass. Screenshots include the overview, dark evaluation and mobile literature view.
- Windows setup (pinned pip install and npm ci), hidden-service start, stop, and restart were executed successfully; both production services are left running locally.
- Original dataset checksum is unchanged. Credential scan found no OpenAlex key outside the ignored `.env`; production npm audit reported zero vulnerabilities.

Metrics: `artifacts/evaluation.json`. Browser results: `verification/browser-results.json`. Tests: `tests/` and `frontend/tests/`. The repository includes reproducible data/model artifacts and a twelve-image screenshot gallery under `docs/screenshots/`; temporary verification captures and runtime files are excluded.

Scope limits: Chromium on this Windows machine was tested; Firefox/Safari and every viewport were not exhaustively tested. Statistical modelling quality is not scientific validation. A Starlette/HTTPX test-client deprecation warning is harmless and does not affect actual API requests. Language/generic vocabulary can affect topics and hypothesis rankings; human review is required.
