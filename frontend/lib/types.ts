export type Model = 'nmf' | 'lda';
export interface Paper {
  paper_id: string; title: string; abstract: string; publication_year: number;
  keywords: string[]; research_topic: string; doi: string; citation_count: number;
  text_source: string; nmf_topic: number; lda_topic: number; abstract_missing: boolean;
}
export interface Topic {
  id: number; label: string; words: { term: string; weight: number }[];
  paper_count: number; mean_weight: number; representative_ids: string[]; coherence_npmi_full: number;
}
export interface Metrics {
  coherence_npmi: number; topic_diversity: number; seed_stability_cosine: number;
  interpretability_proxy: number; heldout_documents: number; training_documents: number;
  heldout_perplexity?: number; heldout_rmse?: number; fit_seconds: number;
}
export interface YearRow {
  year: number; sample_count: number; model_eligible_count: number; abstract_count: number; corpus_count: number;
  topics: { id: number; prevalence: number; lower: number; upper: number; abstract_only_prevalence: number; dominant_count: number }[];
}
export interface Gap {
  id: string; rank: number; topic_a: number; topic_b: number; label_a: string; label_b: string;
  score: number; expected_independence: number; observed: number; deficit_fraction: number;
  base_score: number; semantic_affinity: number;
  balance: number; a_count: number; b_count: number; eligible_count: number; threshold: number;
  intersection_with_title_only: number; threshold_sensitivity: Record<string, number>;
  explanation: string; support_a?: Paper[]; support_b?: Paper[]; counter_evidence?: Paper[];
  yearly: { year: number; a_count: number; b_count: number; intersection_count: number }[];
}
export interface Overview {
  total_papers: number; abstract_papers: number; title_only_papers: number; model_eligible: number;
  zero_feature_papers: number; vocabulary_size: number; topic_count: number; gap_count: number;
  generated_at: string; dataset_sha256: string; training_seconds: number;
  years: YearRow[]; top_topics: Topic[]; featured_gap: Gap | null; methodology: Record<string, string>;
}
export interface Network {
  nodes: { id: string; label: string; count: number; importance: number; centrality: number; x: number; y: number }[];
  edges: { source: string; target: string; weight: number; jaccard: number }[];
  method: string; all_edges_count: number;
}
