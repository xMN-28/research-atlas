# CEP 2 presentation guide

Run `start.bat` and open http://127.0.0.1:3000. The six groups below describe the core analysis capabilities. Evaluation has its own page and supports each stage.

| Engineering task | Where to demonstrate | What to explain |
|---|---|---|
| 1. Preprocessing and features | Literature explorer → title-only filter; Evaluation → preprocessing/features | 10,000 records preserved; 2,421 missing abstracts flagged. Titles used without inventing abstracts. TF-IDF captures discriminative unigram/bigram patterns. 227 zero-feature records remain searchable but unassigned. |
| 2. Topic modelling | Topic discovery → NMF/LDA switch, terms and representative paper; Evaluation | Labels derive from learned terms. NMF uses TF-IDF; LDA uses counts. Actual held-out coherence is 0.3311 vs 0.1363. Some topics reflect language or generic methods. |
| 3. Temporal analysis | Trends → topic/date filters, abstract-only toggle, volume chart | Mean normalized weights measure sampled composition. Equal 1,250/year sampling cannot prove corpus growth. Separate unsampled volume counts are preserved; sample intervals omit model uncertainty. |
| 4. Technical term extraction | Concept network → select a term and inspect linked papers | Terms come from actual TF-IDF mass over a learned vocabulary, with document frequencies and source evidence. They are statistical candidates, not a hand-authored ontology. |
| 5. Concept relationships | Concept network → zoom, drag, change threshold, select connected terms | NetworkX builds document co-occurrences; node size is frequency and edge width is Jaccard. Association is not causation. |
| 6. Research-gap hypotheses | Research gaps → rank, margins, affinity, sensitivities and counter-evidence | 36 review leads combine deficit, support balance/size and learned affinity. Existing intersection papers challenge novelty. No automatically validated research-gap claim. |

Suggested 8–10 minute sequence:

1. Overview: establish real dataset size, years and saved-model status.
2. Literature: search `neural`, select a year, show an abstract and original OpenAlex/DOI reference. Switch text coverage to explain missing abstracts.
3. Topics: compare NMF/LDA terms and inspect a representative paper. Labels can change after retraining.
4. Trends: show sample prevalence and corpus volume side by side; explain their different denominators.
5. Network: select a concept, inspect supporting papers and demonstrate zoom/drag/threshold.
6. Gaps: show marginal-theme literature and existing intersection papers. Explain an alternative reason for a deficit before suggesting an unanswered question.
7. Evaluation: compare real metrics, export JSON and describe methodological limits.

Be explicit about limits: no full-text corpus, no ground-truth gap labels, restricted indexed/classified coverage, multilingual effects, cumulative citation bias, no causal inference and no proof of novelty. This is an inspectable research-assistance system requiring expert review.
