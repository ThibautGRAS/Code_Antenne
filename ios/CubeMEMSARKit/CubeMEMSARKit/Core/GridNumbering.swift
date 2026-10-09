import Foundation
import simd

// "Grille régulière" option: the confirmed microphones are matched to a columns × rows grid
// fitted on the face. Spacings need not be equal (columns and rows), columns need not be
// perfectly straight: microphones are first grouped into columns/rows by the gaps between them;
// with all columns seen, their order alone gives the slots. With a partial scan, the observed
// groups are placed into the slots so that they best follow a uniform spacing (missing ones get
// the interpolated position). Every column and row is then moved to the median of its members.
// Each microphone takes the number of its slot (rightmost column first, bottom to top), so a
// missing microphone leaves a hole instead of shifting every following number.
// The exported positions are always the measured ones. Python reference: tools/replay/grille.py.

struct GridLayout: Equatable {
    var columns = 12
    var rows = 8
    var count: Int { columns * rows }
}

struct GridNumberingResult {
    /// Assigned microphones, `number` = slot (1 … columns × rows).
    var microphones: [NumberedMicrophone]
    /// Slots with no microphone yet.
    var missing: [Int]
    /// Microphones too far from any slot, or second candidate for an occupied slot.
    var unassigned: Int
    /// Not enough coverage to know which observed column/row is which (partial scan).
    var ambiguous: Bool
}

enum GridNumbering {
    /// Fits teeth t_j = origin + j · spacing (j = 0 … count-1, increasing) on 1D positions.
    /// The spacing is searched within ±30 % of `expectedSpacing`; when several alignments fit
    /// the data, the one closest to `center` that stays within ±`halfExtent` is kept.
    static func fitComb(
        _ values: [Float],
        count: Int,
        expectedSpacing: Float,
        center: Float,
        halfExtent: Float
    ) -> (teeth: [Float], spacing: Float, ambiguous: Bool)? {
        guard values.count >= 2, count >= 2, expectedSpacing > 0 else { return nil }

        var best: (cost: Float, spacing: Float, base: Float, kMin: Int, kMax: Int)?
        var spacing = 0.7 * expectedSpacing
        while spacing <= 1.3 * expectedSpacing {
            var sinSum: Float = 0, cosSum: Float = 0
            for v in values {
                let angle = 2 * Float.pi * v / spacing
                sinSum += sin(angle)
                cosSum += cos(angle)
            }
            let base = atan2(sinSum, cosSum) / (2 * Float.pi) * spacing
            var cost: Float = 0
            var kMin = Int.max, kMax = Int.min
            for v in values {
                let k = ((v - base) / spacing).rounded()
                let r = (v - base - k * spacing) / spacing
                cost += min(r * r, 0.09)
                kMin = min(kMin, Int(k))
                kMax = max(kMax, Int(k))
            }
            if kMax - kMin + 1 <= count, best == nil || cost < best!.cost - 1e-9 {
                best = (cost, spacing, base, kMin, kMax)
            }
            spacing += 0.002
        }
        guard let fit = best else { return nil }

        func teeth(_ k0: Int) -> [Float] {
            (0..<count).map { fit.base + Float(k0 + $0) * fit.spacing }
        }
        let feasible = Array((fit.kMax - count + 1)...fit.kMin)
        let inside = feasible.filter { k0 in teeth(k0).allSatisfy { abs($0 - center) <= halfExtent + 0.05 } }
        let candidates = inside.isEmpty ? feasible : inside
        guard let k0 = candidates.min(by: {
            abs(teeth($0).reduce(0, +) / Float(count) - center) < abs(teeth($1).reduce(0, +) / Float(count) - center)
        }) else { return nil }

        return (teeth(k0), fit.spacing, candidates.count > 1)
    }

    /// Half the gap to the neighboring teeth (both sides averaged): how far a member may be.
    static func localHalfGaps(_ teeth: [Float]) -> [Float] {
        teeth.indices.map { j in
            var gaps: [Float] = []
            if j > 0 { gaps.append(teeth[j] - teeth[j - 1]) }
            if j < teeth.count - 1 { gaps.append(teeth[j + 1] - teeth[j]) }
            return 0.5 * gaps.reduce(0, +) / Float(max(1, gaps.count))
        }
    }

    /// Moves every tooth to the median of its members (irregular spacing), keeping the order.
    static func refine(_ values: [Float], teeth start: [Float], iterations: Int = 4) -> [Float] {
        var teeth = start
        for _ in 0..<iterations {
            let gates = localHalfGaps(teeth).map { 0.9 * $0 }
            var members = [[Float]](repeating: [], count: teeth.count)
            for v in values {
                guard let j = teeth.indices.min(by: { abs(v - teeth[$0]) < abs(v - teeth[$1]) }),
                      abs(v - teeth[j]) <= gates[j] else { continue }
                members[j].append(v)
            }
            var updated = teeth
            for j in teeth.indices where !members[j].isEmpty {
                let sorted = members[j].sorted()
                updated[j] = sorted[sorted.count / 2]
            }
            // Keep the teeth ordered and apart (an empty tooth keeps its comb position).
            if zip(updated, updated.dropFirst()).allSatisfy({ $0 < $1 }) {
                teeth = updated
            }
        }
        return teeth
    }

    /// Splits sorted 1D positions where the gap exceeds `minGap`; returns the group medians.
    static func clusters(_ values: [Float], minGap: Float) -> [Float] {
        let sorted = values.sorted()
        guard let first = sorted.first else { return [] }
        var groups: [[Float]] = [[first]]
        for (a, b) in zip(sorted, sorted.dropFirst()) {
            if b - a > minGap {
                groups.append([b])
            } else {
                groups[groups.count - 1].append(b)
            }
        }
        return groups.map { $0[$0.count / 2] }
    }

    /// Order-preserving placement of observed group centers into `count` slots: the choice whose
    /// centers best follow a uniform spacing (within ±35 % of `expectedSpacing`, inside the face).
    /// Missing slots get the interpolated position. nil when there are more groups than slots.
    static func place(
        _ centers: [Float],
        count: Int,
        expectedSpacing: Float,
        halfExtent: Float
    ) -> (teeth: [Float], ambiguous: Bool)? {
        let n = centers.count
        guard n > 0, n <= count else { return nil }
        if n == count { return (centers, false) }

        var results: [(cost: Float, teeth: [Float])] = []
        var chosen: [Int] = []

        func evaluate() {
            let idx = chosen.map(Float.init)
            var a: Float, b: Float
            if n >= 2 {
                let mi = idx.reduce(0, +) / Float(n), mc = centers.reduce(0, +) / Float(n)
                var sxy: Float = 0, sxx: Float = 0
                for (i, c) in zip(idx, centers) {
                    sxy += (i - mi) * (c - mc)
                    sxx += (i - mi) * (i - mi)
                }
                b = sxy / sxx
                a = mc - b * mi
            } else {
                b = expectedSpacing
                a = centers[0] - b * idx[0]
            }
            guard b >= 0.65 * expectedSpacing, b <= 1.35 * expectedSpacing else { return }
            var teeth = (0..<count).map { a + b * Float($0) }
            guard teeth.allSatisfy({ abs($0) <= halfExtent + 0.05 }) else { return }
            var cost: Float = 0
            for (i, c) in zip(idx, centers) {
                cost += (c - (a + b * i)) * (c - (a + b * i))
            }
            cost = cost / (b * b) + 0.05 * abs(teeth.reduce(0, +) / Float(count))
            for (k, c) in zip(chosen, centers) {
                teeth[k] = c
            }
            results.append((cost, teeth))
        }

        func search(_ start: Int) {
            if chosen.count == n {
                evaluate()
                return
            }
            guard start <= count - (n - chosen.count) else { return }
            for k in start...(count - (n - chosen.count)) {
                chosen.append(k)
                search(k + 1)
                chosen.removeLast()
            }
        }
        search(0)

        let sorted = results.sorted { $0.cost < $1.cost }
        guard let best = sorted.first else { return nil }
        let ambiguous = sorted.count > 1 && sorted[1].cost < 1.5 * best.cost + 0.01
        return (best.teeth, ambiguous)
    }

    /// Slots of one axis: gap groups placed into the slots, uniform-comb fallback, then refined.
    static func axis(
        _ values: [Float],
        count: Int,
        size: Float
    ) -> (teeth: [Float], ambiguous: Bool)? {
        let expected = size * 0.85 / Float(max(1, count - 1))
        if let placed = place(
            clusters(values, minGap: 0.4 * expected),
            count: count, expectedSpacing: expected, halfExtent: size / 2
        ) {
            return (refine(values, teeth: placed.teeth), placed.ambiguous)
        }
        guard let comb = fitComb(values, count: count, expectedSpacing: expected, center: 0, halfExtent: size / 2) else {
            return nil
        }
        return (refine(values, teeth: comb.teeth), comb.ambiguous)
    }

    static func number(
        _ tracks: [MicroTrack],
        layout: GridLayout,
        faceWidth: Float,
        faceHeight: Float
    ) -> GridNumberingResult {
        let confirmed = tracks.indices.compactMap { index -> (index: Int, local: SIMD3<Float>)? in
            guard tracks[index].state == .confirmed, let local = tracks[index].localPoint else { return nil }
            return (index, local)
        }
        let allSlots = Array(1...layout.count)
        let empty = GridNumberingResult(microphones: [], missing: allSlots, unassigned: confirmed.count, ambiguous: true)

        let xs = confirmed.map { $0.local.x }
        let ys = confirmed.map { $0.local.y }
        guard
            xs.count >= 2,
            let columnsFit = axis(xs, count: layout.columns, size: faceWidth),
            let rowsFit = axis(ys, count: layout.rows, size: faceHeight)
        else { return empty }

        let columnX = columnsFit.teeth
        let rowY = rowsFit.teeth
        let columnGates = localHalfGaps(columnX).map { 0.9 * $0 }
        let rowGates = localHalfGaps(rowY).map { 0.9 * $0 }

        var bySlot: [Int: (index: Int, local: SIMD3<Float>)] = [:]
        var unassigned = 0
        for point in confirmed {
            guard
                let j = columnX.indices.min(by: { abs(point.local.x - columnX[$0]) < abs(point.local.x - columnX[$1]) }),
                let r = rowY.indices.min(by: { abs(point.local.y - rowY[$0]) < abs(point.local.y - rowY[$1]) }),
                abs(point.local.x - columnX[j]) <= columnGates[j],
                abs(point.local.y - rowY[r]) <= rowGates[r]
            else {
                unassigned += 1
                continue
            }
            // Column 0 = rightmost when facing the grid, row 0 = bottom.
            let column = layout.columns - 1 - j
            let slot = column * layout.rows + r + 1
            if let existing = bySlot[slot] {
                // Keep the better-constrained microphone for this slot.
                if tracks[point.index].uncertainty < tracks[existing.index].uncertainty {
                    bySlot[slot] = point
                }
                unassigned += 1
            } else {
                bySlot[slot] = point
            }
        }

        let microphones = bySlot.keys.sorted().map { slot -> NumberedMicrophone in
            let point = bySlot[slot]!
            let track = tracks[point.index]
            return NumberedMicrophone(
                number: slot,
                trackIndex: point.index,
                column: (slot - 1) / layout.rows + 1,
                row: (slot - 1) % layout.rows + 1,
                position: point.local,
                uncertainty: track.uncertainty,
                rays: track.rays.count,
                residual: track.residual
            )
        }

        return GridNumberingResult(
            microphones: microphones,
            missing: allSlots.filter { bySlot[$0] == nil },
            unassigned: unassigned,
            ambiguous: columnsFit.ambiguous || rowsFit.ambiguous
        )
    }
}
