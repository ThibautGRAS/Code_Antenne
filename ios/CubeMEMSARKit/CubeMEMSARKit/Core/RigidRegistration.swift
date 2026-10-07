import Foundation
import simd

// Re-registration of the exported microphones into the real antenna frame from a few
// reference channels of known position (same method as tools/recalage/recaler_repere.py):
// rigid fit (rotation + translation, no scale) by Horn's quaternion method.

struct RigidTransform {
    var rotation: simd_double3x3
    var translation: SIMD3<Double>

    static let identity = RigidTransform(rotation: matrix_identity_double3x3, translation: .zero)

    func apply(_ point: SIMD3<Float>) -> SIMD3<Float> {
        SIMD3<Float>(rotation * SIMD3<Double>(point) + translation)
    }

    var rotationDegrees: Double {
        let cosine = (rotation.columns.0.x + rotation.columns.1.y + rotation.columns.2.z - 1) / 2
        return acos(min(1, max(-1, cosine))) * 180 / .pi
    }
}

enum RigidRegistration {
    /// R, t minimizing Σ|R·sourceᵢ + t − targetᵢ|². Needs ≥ 3 non-collinear points.
    static func fit(source: [SIMD3<Double>], target: [SIMD3<Double>]) -> RigidTransform? {
        guard source.count == target.count, source.count >= 3 else { return nil }

        let n = Double(source.count)
        let sourceCenter = source.reduce(SIMD3<Double>.zero, +) / n
        let targetCenter = target.reduce(SIMD3<Double>.zero, +) / n

        // Cross-covariance S[a][b] = Σ p_a q_b of the centered points.
        var S = [[Double]](repeating: [0, 0, 0], count: 3)
        for (p0, q0) in zip(source, target) {
            let p = p0 - sourceCenter
            let q = q0 - targetCenter
            for a in 0..<3 {
                for b in 0..<3 {
                    S[a][b] += p[a] * q[b]
                }
            }
        }

        let (xx, xy, xz) = (S[0][0], S[0][1], S[0][2])
        let (yx, yy, yz) = (S[1][0], S[1][1], S[1][2])
        let (zx, zy, zz) = (S[2][0], S[2][1], S[2][2])
        let N: [[Double]] = [
            [xx + yy + zz, yz - zy, zx - xz, xy - yx],
            [yz - zy, xx - yy - zz, xy + yx, zx + xz],
            [zx - xz, xy + yx, -xx + yy - zz, yz + zy],
            [xy - yx, zx + xz, yz + zy, -xx - yy + zz]
        ]

        let q = largestEigenvector(N)
        let rotation = simd_double3x3(simd_quatd(ix: q[1], iy: q[2], iz: q[3], r: q[0]).normalized)
        return RigidTransform(rotation: rotation, translation: targetCenter - rotation * sourceCenter)
    }

    /// Largest distance from a point to the line through the two farthest-apart points.
    static func collinearity(_ points: [SIMD3<Double>]) -> Double {
        guard points.count >= 3 else { return 0 }
        var (a, b) = (points[0], points[1])
        var best = 0.0
        for i in points.indices {
            for j in points.indices where j > i {
                let d = simd_distance(points[i], points[j])
                if d > best {
                    best = d
                    (a, b) = (points[i], points[j])
                }
            }
        }
        guard best > 0 else { return 0 }
        let direction = (b - a) / best
        return points.map { simd_length(simd_cross($0 - a, direction)) }.max() ?? 0
    }

    /// Eigenvector of the largest eigenvalue of a symmetric 4×4 matrix (cyclic Jacobi).
    private static func largestEigenvector(_ input: [[Double]]) -> [Double] {
        var a = input
        var v: [[Double]] = (0..<4).map { i in (0..<4).map { $0 == i ? 1 : 0 } }

        for _ in 0..<50 {
            var offDiagonal = 0.0
            for p in 0..<4 { for q in (p + 1)..<4 { offDiagonal += a[p][q] * a[p][q] } }
            if offDiagonal < 1e-22 { break }

            for p in 0..<4 {
                for q in (p + 1)..<4 where abs(a[p][q]) > 1e-300 {
                    let theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                    let t = (theta >= 0 ? 1.0 : -1.0) / (abs(theta) + sqrt(theta * theta + 1))
                    let c = 1 / sqrt(t * t + 1)
                    let s = t * c

                    for k in 0..<4 {
                        let akp = a[k][p], akq = a[k][q]
                        a[k][p] = c * akp - s * akq
                        a[k][q] = s * akp + c * akq
                    }
                    for k in 0..<4 {
                        let apk = a[p][k], aqk = a[q][k]
                        a[p][k] = c * apk - s * aqk
                        a[q][k] = s * apk + c * aqk
                    }
                    for k in 0..<4 {
                        let vkp = v[k][p], vkq = v[k][q]
                        v[k][p] = c * vkp - s * vkq
                        v[k][q] = s * vkp + c * vkq
                    }
                }
            }
        }

        let best = (0..<4).max { a[$0][$0] < a[$1][$1] } ?? 0
        return (0..<4).map { v[$0][best] }
    }
}

// MARK: - Registration from reference channels

struct ReferenceRegistration {
    var transform: RigidTransform
    /// Distance (mm) between each reference and its registered microphone, by channel.
    var residualsMm: [Int: Double]
    var rmsMm: Double
    var translationOnly: Bool
}

enum ReferenceRegistrationError: Error, Equatable {
    case noReference
    case twoReferences
    case collinear
    case missingChannels([Int])
}

extension RigidRegistration {
    /// 1 reference: translation only. 2: refused (rotation undetermined). ≥ 3 non-collinear: rigid fit.
    static func register(
        microphones: [NumberedMicrophone],
        references: [Int: SIMD3<Double>]
    ) -> Result<ReferenceRegistration, ReferenceRegistrationError> {
        guard !references.isEmpty else { return .failure(.noReference) }

        let byNumber = Dictionary(uniqueKeysWithValues: microphones.map { ($0.number, $0) })
        let channels = references.keys.sorted()
        let missing = channels.filter { byNumber[$0] == nil }
        guard missing.isEmpty else { return .failure(.missingChannels(missing)) }

        let source = channels.map { SIMD3<Double>(byNumber[$0]!.position) }
        let target = channels.map { references[$0]! }

        let transform: RigidTransform
        switch channels.count {
        case 1:
            transform = RigidTransform(rotation: matrix_identity_double3x3, translation: target[0] - source[0])
        case 2:
            return .failure(.twoReferences)
        default:
            guard collinearity(source) > 0.05, let fitted = fit(source: source, target: target) else {
                return .failure(.collinear)
            }
            transform = fitted
        }

        var residuals: [Int: Double] = [:]
        var sumSquared = 0.0
        for (index, channel) in channels.enumerated() {
            let moved = transform.rotation * source[index] + transform.translation
            let error = simd_distance(moved, target[index]) * 1000
            residuals[channel] = error
            sumSquared += error * error
        }

        return .success(
            ReferenceRegistration(
                transform: transform,
                residualsMm: residuals,
                rmsMm: sqrt(sumSquared / Double(channels.count)),
                translationOnly: channels.count == 1
            )
        )
    }
}
