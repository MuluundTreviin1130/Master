from __future__ import annotations

from typing import Tuple

import numpy as np


def _standardize(feature_matrix: np.ndarray) -> np.ndarray:
    if feature_matrix.size == 0:
        return feature_matrix
    mu = feature_matrix.mean(axis=0, keepdims=True)
    sigma = feature_matrix.std(axis=0, keepdims=True)
    sigma[sigma <= 1e-12] = 1.0
    return (feature_matrix - mu) / sigma


def standardized_distance_matrix(
    feature_matrix: np.ndarray,
    *,
    metric: str = "standardized_euclidean",
) -> np.ndarray:
    x = _standardize(np.asarray(feature_matrix, dtype=float))
    if x.ndim != 2:
        raise ValueError("[dispatch.scenarios] feature_matrix must be 2D.")
    n = x.shape[0]
    d = np.zeros((n, n), dtype=float)
    key = str(metric or "standardized_euclidean").strip().lower()
    if key not in {"standardized_euclidean", "standardized_manhattan"}:
        raise ValueError(f"[dispatch.scenarios] Unsupported distance metric '{metric}'.")
    for i in range(n):
        diff = x[i + 1 :] - x[i]
        if key == "standardized_euclidean":
            dist = np.sqrt(np.sum(diff * diff, axis=1))
        else:
            dist = np.sum(np.abs(diff), axis=1)
        d[i, i + 1 :] = dist
        d[i + 1 :, i] = dist
    return d


def _fast_forward(distance_matrix: np.ndarray, probabilities: np.ndarray, n_select: int) -> np.ndarray:
    n = distance_matrix.shape[0]
    if n_select >= n:
        return np.arange(n, dtype=int)
    remaining = set(range(n))
    selected: list[int] = []
    best_distance = np.full(n, np.inf, dtype=float)
    for _ in range(n_select):
        best_idx = None
        best_score = np.inf
        for cand in remaining:
            candidate_distance = np.minimum(best_distance, distance_matrix[:, cand])
            score = float(np.sum(probabilities * candidate_distance))
            if score < best_score:
                best_score = score
                best_idx = cand
        if best_idx is None:
            break
        selected.append(best_idx)
        remaining.remove(best_idx)
        best_distance = np.minimum(best_distance, distance_matrix[:, best_idx])
    return np.asarray(sorted(selected), dtype=int)


def _greedy_kmedoids(distance_matrix: np.ndarray, probabilities: np.ndarray, n_select: int) -> np.ndarray:
    n = distance_matrix.shape[0]
    if n_select >= n:
        return np.arange(n, dtype=int)
    selected: list[int] = []
    remaining = set(range(n))
    while len(selected) < n_select and remaining:
        best_idx = None
        best_score = np.inf
        for cand in remaining:
            medoids = selected + [cand]
            dist = np.min(distance_matrix[:, medoids], axis=1)
            score = float(np.sum(probabilities * dist))
            if score < best_score:
                best_score = score
                best_idx = cand
        selected.append(int(best_idx))
        remaining.remove(int(best_idx))
    return np.asarray(sorted(selected), dtype=int)


def reduce_scenarios(
    feature_matrix: np.ndarray,
    probabilities: np.ndarray,
    n_select: int,
    method: str = "fast_forward",
    *,
    metric: str = "standardized_euclidean",
) -> Tuple[np.ndarray, np.ndarray]:
    feature_matrix = np.asarray(feature_matrix, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float).reshape(-1)
    if feature_matrix.ndim != 2:
        raise ValueError("[dispatch.scenarios] feature_matrix must be 2D.")
    n = feature_matrix.shape[0]
    if probabilities.size != n:
        raise ValueError("[dispatch.scenarios] probability count does not match scenario count.")
    if n == 0:
        return np.zeros(0, dtype=int), np.zeros(0, dtype=float)
    if n_select <= 0:
        raise ValueError("[dispatch.scenarios] n_select must be > 0.")

    prob_sum = float(np.sum(probabilities))
    if prob_sum <= 0.0:
        probabilities = np.full(n, 1.0 / n, dtype=float)
    else:
        probabilities = probabilities / prob_sum

    dist = standardized_distance_matrix(feature_matrix, metric=metric)
    key = str(method or "fast_forward").strip().lower()
    if key == "fast_forward":
        selected = _fast_forward(dist, probabilities, n_select)
    elif key == "kmedoids":
        selected = _greedy_kmedoids(dist, probabilities, n_select)
    else:
        raise ValueError(f"[dispatch.scenarios] Unsupported reduction method '{method}'.")

    reduced_prob = np.zeros(selected.size, dtype=float)
    if selected.size == 0:
        return selected, reduced_prob
    for i in range(n):
        nearest = int(np.argmin(dist[i, selected]))
        reduced_prob[nearest] += probabilities[i]
    return selected, reduced_prob
