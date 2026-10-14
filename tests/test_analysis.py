import numpy as np
import pytest
from scipy.sparse import csr_matrix
from literature_mining.analysis import gap_metrics, normalize_weights, npmi, stability, normalize_documents


def test_preprocessing_stopwords_and_no_imputation():
    result = normalize_documents(['A novel neural network'], [''])
    assert 'neural' in result[0] and 'network' in result[0]
    assert 'the' not in result[0].split()
    assert 'nan' not in result[0]


def test_normalization_does_not_assign_empty_documents():
    result = normalize_weights(np.array([[1., 3.], [0., 0.]]))
    np.testing.assert_allclose(result, [[0.25, 0.75], [0, 0]])


def test_coherence_independence_and_missing_pair():
    independent = csr_matrix([[1, 1], [1, 0], [0, 1], [0, 0]])
    assert npmi(independent, [0, 1]) == pytest.approx(0)
    disjoint = csr_matrix([[1, 0], [0, 1]])
    assert npmi(disjoint, [0, 1]) == -1


def test_stability_matches_permuted_topics():
    topics = np.eye(3)
    assert stability(topics, topics[[2, 0, 1]]) == pytest.approx(1)


def test_gap_score_deficit_and_balanced_support():
    assert gap_metrics(1000, 200, 100, 20)['score'] == 0
    low = gap_metrics(1000, 200, 100, 2)
    assert low['expected_independence'] == 20
    assert 0 < low['score'] < 1
