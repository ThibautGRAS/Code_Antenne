import Foundation
import simd

// Virtual antenna: ground-truth capsules + distractors around one face, synthetic detections
// from a pinhole camera, and scoring of a reconstruction against the ground truth.
// Used by the app's "antenne virtuelle" test mode (real ARKit poses, no real antenna)
// and by the CI scan simulator.

// MARK: - Deterministic random numbers

struct SplitMix64: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    mutating func uniform(_ range: ClosedRange<Float>) -> Float {
        Float.random(in: range, using: &self)
    }

    mutating func chance(_ probability: Float) -> Bool {
        Float.random(in: 0..<1, using: &self) < probability
    }

    mutating func gaussian(sigma: Float) -> Float {
        let u1 = max(Float.random(in: 0..<1, using: &self), 1e-7)
        let u2 = Float.random(in: 0..<1, using: &self)
        return sigma * sqrt(-2 * log(u1)) * cos(2 * Float.pi * u2)
    }
}

// MARK: - Scene

enum VirtualTargetKind: Equatable {
    /// Capsule of the scanned face (ground truth).
    case capsule
    /// Capsule of the opposite face, seen through the net.
    case backCapsule
    /// White object of the anechoic room.
    case clutter
}

struct VirtualTarget {
    var kind: VirtualTargetKind
    /// Position in the face frame (Z = face normal, toward the operator).
    var local: SIMD3<Float>
    var diameter: Float
}

/// Pinhole camera with ARKit conventions: camera-to-world transform looking along -Z,
/// X right, Y up; intrinsics in pixels of the captured image (origin top-left, v down).
struct PinholeCamera {
    var transform: simd_float4x4
    var intrinsics: simd_float3x3
    var imageSize: SIMD2<Float>
}

struct DetectorModel {
    var detectionProbability: Float = 0.85
    var distractorDetectionProbability: Float = 0.6
    var pixelNoise: Float = 1.5
    var sizeNoise: Float = 0.15
}

struct SyntheticDetection {
    var kind: VirtualTargetKind
    var origin: SIMD3<Float>
    var direction: SIMD3<Float>
    var diameterPixels: Float
}

struct VirtualAntenna {
    var targets: [VirtualTarget]

    var capsulePositions: [SIMD3<Float>] {
        targets.filter { $0.kind == .capsule }.map { $0.local }
    }

    static func make(
        faceSize: Float = 2.0,
        planeOffset: Float,
        capsuleDiameter: Float = 0.030,
        columns: Int = 6,
        rows: Int = 7,
        jitter: Float = 0.03,
        closePairs: Int = 0,
        closePairDistance: Float = 0.06,
        backFace: Bool,
        backFaceDepth: Float = 2.0,
        clutterCount: Int,
        clutterDepth: ClosedRange<Float> = 2.3...4.5,
        clutterSpread: Float = 2.5,
        clutterDiameter: ClosedRange<Float> = 0.01...0.12,
        rng: inout SplitMix64
    ) -> VirtualAntenna {
        var targets: [VirtualTarget] = []
        let usable = faceSize * 0.85

        func grid(z: Float, kind: VirtualTargetKind, shift: SIMD2<Float>) {
            for column in 0..<columns {
                for row in 0..<rows {
                    let u = columns > 1 ? Float(column) / Float(columns - 1) - 0.5 : 0
                    let v = rows > 1 ? Float(row) / Float(rows - 1) - 0.5 : 0
                    let x = u * usable + shift.x + rng.uniform(-jitter...jitter)
                    let y = v * usable + shift.y + rng.uniform(-jitter...jitter)
                    targets.append(VirtualTarget(kind: kind, local: SIMD3<Float>(x, y, z), diameter: capsuleDiameter))
                }
            }
        }

        grid(z: planeOffset, kind: .capsule, shift: .zero)

        let originals = targets
        for index in 0..<min(closePairs, originals.count) {
            let base = originals[(index * 7) % originals.count]
            let angle = rng.uniform(0...(2 * Float.pi))
            let offset = SIMD3<Float>(cos(angle), sin(angle), 0) * closePairDistance
            targets.append(VirtualTarget(kind: .capsule, local: base.local + offset, diameter: capsuleDiameter))
        }

        if backFace {
            grid(z: planeOffset - backFaceDepth, kind: .backCapsule, shift: SIMD2<Float>(0.11, -0.07))
        }

        let spread = clutterSpread * faceSize / 2
        for _ in 0..<clutterCount {
            let local = SIMD3<Float>(
                rng.uniform(-spread...spread),
                rng.uniform(-spread...spread),
                planeOffset - rng.uniform(clutterDepth)
            )
            targets.append(VirtualTarget(kind: .clutter, local: local, diameter: rng.uniform(clutterDiameter)))
        }

        return VirtualAntenna(targets: targets)
    }

    /// What a white-blob detector would return for this camera pose, sorted by decreasing
    /// blob size like CapsuleDetector. Rays start at the camera position.
    func detections(
        face: FaceGeometry,
        camera: PinholeCamera,
        model: DetectorModel,
        rng: inout SplitMix64
    ) -> [SyntheticDetection] {
        let fx = camera.intrinsics.columns.0.x
        let fy = camera.intrinsics.columns.1.y
        let cx = camera.intrinsics.columns.2.x
        let cy = camera.intrinsics.columns.2.y

        let worldToCamera = simd_inverse(camera.transform)
        let rotation = camera.transform.rotation
        let origin = camera.transform.translation

        var result: [SyntheticDetection] = []

        for target in targets {
            let p = worldToCamera.transformPoint(face.transform.transformPoint(target.local))
            let depth = -p.z
            guard depth > 0.15 else { continue }

            let u = cx + fx * p.x / depth
            let v = cy - fy * p.y / depth
            guard u >= 0, u <= camera.imageSize.x, v >= 0, v <= camera.imageSize.y else { continue }

            let probability = target.kind == .capsule
                ? model.detectionProbability
                : model.distractorDetectionProbability
            guard rng.chance(probability) else { continue }

            let noisyU = u + rng.gaussian(sigma: model.pixelNoise)
            let noisyV = v + rng.gaussian(sigma: model.pixelNoise)
            let cameraDirection = simd_normalize(SIMD3<Float>((noisyU - cx) / fx, (cy - noisyV) / fy, -1))
            let diameterPixels = fx * target.diameter / depth * max(0.2, 1 + rng.gaussian(sigma: model.sizeNoise))

            result.append(
                SyntheticDetection(
                    kind: target.kind,
                    origin: origin,
                    direction: simd_normalize(rotation * cameraDirection),
                    diameterPixels: diameterPixels
                )
            )
        }

        result.sort { $0.diameterPixels > $1.diameterPixels }
        return result
    }
}

// MARK: - Scoring against ground truth

struct ScanScore: CustomStringConvertible {
    var capsules = 0
    var confirmed = 0
    var matchedCapsules = 0
    /// Extra confirmed tracks on an already matched capsule.
    var duplicates = 0
    /// Confirmed tracks 3–10 cm from the nearest capsule (badly triangulated capsule).
    var inaccurate = 0
    /// Confirmed tracks more than 10 cm from any capsule (distractor or merged track).
    var falseConfirmed = 0
    var rmsErrorMm: Float = 0
    var maxErrorMm: Float = 0

    var recall: Float {
        capsules == 0 ? 1 : Float(matchedCapsules) / Float(capsules)
    }

    var description: String {
        String(
            format: "capsules=%d confirmed=%d recall=%.0f%% duplicates=%d inaccurate=%d false=%d rms=%.1fmm max=%.1fmm",
            capsules, confirmed, recall * 100, duplicates, inaccurate, falseConfirmed, rmsErrorMm, maxErrorMm
        )
    }
}

enum ReconstructionScorer {
    static let matchRadius: Float = 0.03
    static let nearRadius: Float = 0.10

    /// Matches every confirmed white track to the nearest ground-truth capsule (face frame).
    static func score(
        tracks: [MicroTrack],
        capsules: [SIMD3<Float>],
        face: FaceGeometry
    ) -> ScanScore {
        let worldToFace = simd_inverse(face.transform)

        var score = ScanScore()
        score.capsules = capsules.count

        var matchesPerCapsule = [Int](repeating: 0, count: capsules.count)
        var bestError = [Float](repeating: .greatestFiniteMagnitude, count: capsules.count)

        for track in tracks where track.state == .confirmed && track.kind == .white {
            guard let world = track.worldPoint else { continue }
            score.confirmed += 1

            let local = worldToFace.transformPoint(world)
            var nearest = -1
            var nearestDistance = Float.greatestFiniteMagnitude
            for (index, capsule) in capsules.enumerated() {
                let distance = simd_distance(local, capsule)
                if distance < nearestDistance {
                    nearestDistance = distance
                    nearest = index
                }
            }

            if nearest >= 0, nearestDistance <= matchRadius {
                matchesPerCapsule[nearest] += 1
                bestError[nearest] = min(bestError[nearest], nearestDistance)
            } else if nearestDistance <= nearRadius {
                score.inaccurate += 1
            } else {
                score.falseConfirmed += 1
            }
        }

        var sumSquared: Float = 0
        for index in capsules.indices where matchesPerCapsule[index] > 0 {
            score.matchedCapsules += 1
            score.duplicates += matchesPerCapsule[index] - 1
            sumSquared += bestError[index] * bestError[index]
            score.maxErrorMm = max(score.maxErrorMm, bestError[index] * 1000)
        }
        if score.matchedCapsules > 0 {
            score.rmsErrorMm = sqrt(sumSquared / Float(score.matchedCapsules)) * 1000
        }

        return score
    }
}
