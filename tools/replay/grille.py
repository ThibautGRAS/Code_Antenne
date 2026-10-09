"""Reference (Python) of Core/GridNumbering.swift: matches the confirmed microphones (face-local XY,
meters) to a columns x rows grid and numbers them by slot (rightmost column first, bottom to top).
Spacings need not be equal: a uniform comb gives the starting alignment, then each column and each
row moves to the median of its own microphones. Missing microphones leave holes, not shifts."""
import math

import numpy as np


def fit_comb(values, count, expected, center, half_extent):
    v = np.asarray(values, np.float32)
    if len(v) < 2:
        return None
    best = None
    s = np.float32(0.7 * expected)
    while s <= 1.3 * expected:
        ang = 2 * math.pi * v / s
        base = math.atan2(np.sin(ang).sum(), np.cos(ang).sum()) / (2 * math.pi) * s
        k = np.round((v - base) / s)
        cost = np.minimum(((v - base - k * s) / s) ** 2, 0.09).sum()
        if k.max() - k.min() + 1 <= count and (best is None or cost < best[0] - 1e-9):
            best = (cost, s, base, int(k.min()), int(k.max()))
        s = np.float32(s + 0.002)
    if best is None:
        return None
    _, s, base, kmin, kmax = best
    teeth = lambda k0: [base + (k0 + j) * s for j in range(count)]
    feasible = list(range(kmax - count + 1, kmin + 1))
    inside = [k0 for k0 in feasible if all(abs(t - center) <= half_extent + 0.05 for t in teeth(k0))]
    cand = inside or feasible
    k0 = min(cand, key=lambda k: abs(np.mean(teeth(k)) - center))
    return teeth(k0), s, len(cand) > 1


def local_half_gaps(teeth):
    out = []
    for j in range(len(teeth)):
        gaps = []
        if j > 0: gaps.append(teeth[j] - teeth[j - 1])
        if j < len(teeth) - 1: gaps.append(teeth[j + 1] - teeth[j])
        out.append(0.5 * sum(gaps) / max(1, len(gaps)))
    return out


def refine(values, teeth, iterations=4):
    teeth = list(teeth)
    for _ in range(iterations):
        gates = [0.9 * g for g in local_half_gaps(teeth)]
        members = [[] for _ in teeth]
        for v in values:
            j = int(np.argmin([abs(v - t) for t in teeth]))
            if abs(v - teeth[j]) <= gates[j]:
                members[j].append(v)
        updated = [sorted(m)[len(m) // 2] if m else t for m, t in zip(members, teeth)]
        if all(a < b for a, b in zip(updated, updated[1:])):
            teeth = updated
    return teeth


def clusters(values, min_gap):
    """Splits sorted 1D positions where the gap exceeds min_gap; returns cluster medians."""
    v = sorted(float(x) for x in values)
    groups = [[v[0]]] if v else []
    for a, b in zip(v, v[1:]):
        if b - a > min_gap: groups.append([b])
        else: groups[-1].append(b)
    return [g[len(g) // 2] for g in groups]


def place(centers, count, expected, half_extent):
    """Order-preserving placement of observed cluster centers into `count` slots: the choice whose
    centers best follow a uniform comb (spacing within +-35 % of expected, inside the face).
    Missing slots get the comb position. Returns (teeth, ambiguous) or None."""
    n = len(centers)
    if n == 0 or n > count:
        return None
    if n == count:
        return list(centers), False
    results = []
    def rec(start, chosen):
        if len(chosen) == n:
            idx = np.array(chosen, float); c = np.array(centers)
            if n >= 2:
                b, a = np.polyfit(idx, c, 1)
            else:
                b, a = expected, c[0] - expected * idx[0]
            if not (0.65 * expected <= b <= 1.35 * expected): return
            teeth = [a + b * k for k in range(count)]
            if any(abs(t) > half_extent + 0.05 for t in teeth): return
            cost = float(np.sum((c - (a + b * idx)) ** 2)) / b ** 2 + 0.05 * abs(np.mean(teeth))
            for k, ci in zip(chosen, centers): teeth[k] = ci
            results.append((cost, teeth))
            return
        for k in range(start, count - (n - len(chosen)) + 1):
            rec(k + 1, chosen + [k])
    rec(0, [])
    if not results: return None
    results.sort(key=lambda r: r[0])
    ambiguous = len(results) > 1 and results[1][0] < 1.5 * results[0][0] + 0.01
    return results[0][1], ambiguous


def number(points, uncertainties=None, columns=12, rows=8, width=1.95, height=1.83):
    """points: [(x, y)] -> ({slot: point index}, missing slots, unassigned, ambiguous)."""
    P = np.asarray(points, np.float32)
    unc = uncertainties if uncertainties is not None else [0.0] * len(P)
    if len(P) < 2:
        return {}, list(range(1, columns * rows + 1)), len(P), True
    axes = []
    for values, count, size in ((P[:, 0], columns, width), (P[:, 1], rows, height)):
        expected = size * 0.85 / (count - 1)
        placed = place(clusters(values, 0.4 * expected), count, expected, size / 2)
        if placed is None:                       # too many clusters (noise): uniform comb fallback
            comb = fit_comb(values, count, expected, 0.0, size / 2)
            if comb is None:
                return {}, list(range(1, columns * rows + 1)), len(P), True
            placed = (comb[0], comb[2])
        axes.append((refine(values, placed[0]), placed[1]))
    (cx, ambx), (ry, amby) = axes
    gx = [0.9 * g for g in local_half_gaps(cx)]
    gy = [0.9 * g for g in local_half_gaps(ry)]
    slots, unassigned = {}, 0
    for i, (x, y) in enumerate(P):
        j = int(np.argmin([abs(x - c) for c in cx]))
        r = int(np.argmin([abs(y - c) for c in ry]))
        if abs(x - cx[j]) > gx[j] or abs(y - ry[r]) > gy[r]:
            unassigned += 1
            continue
        slot = (columns - 1 - j) * rows + r + 1
        if slot in slots:
            unassigned += 1
            if unc[i] < unc[slots[slot]]:
                slots[slot] = i
        else:
            slots[slot] = i
    missing = [k for k in range(1, columns * rows + 1) if k not in slots]
    return slots, missing, unassigned, ambx or amby
