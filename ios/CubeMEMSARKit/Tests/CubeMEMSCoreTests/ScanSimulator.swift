import Foundation
import simd
@testable import CubeMEMSCore

// Synthetic walk-around scan of one cube face. It replaces ARKit + CapsuleDetector by
// ground-truth geometry (camera poses, capsule and distractor positions) and feeds the
// reconstruction core exactly like ARScannerView.consume(detections:frame:) does.

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

enum SimTargetKind: Equatable {
    /// Capsule of the scanned face (ground truth).
    case capsule
    /// Capsule of the opposite face, seen through the net.
    case backCapsule
    /// White object of the anechoic room.
    case clutter
}

struct SimTarget {
    var kind: SimTargetKind
    /// Position in the face frame (Z = face normal, toward the camera).
    var local: SIMD3<Float>
    var diameter: Float
}

struct ScanScenario {
    var name: String
    var seed: UInt64 = 42

    // Timing: the app runs the detector at most every 0.2 s on a 60 Hz ARKit stream.
    var duration: Float = 60
    var tickInterval: Float = 0.2
    var framesPerTick = 12

    // Face
    var faceSize: Float = 2.0
    var planeOffset: Float = 0.03
    var capsuleColumns = 6
    var capsuleRows = 7
    var capsuleJitter: Float = 0.03
    var capsuleDiameter: Float = 0.030
    /// Extra capsules placed `closePairDistance` away from existing ones.
    var closePairs = 0
    var closePairDistance: Float = 0.06

    // Distractors
    var backFace = false
    var backFaceDepth: Float = 2.0
    var clutterCount = 0
    var clutterDepth: ClosedRange<Float> = 2.3...4.5
    var clutterSpread: Float = 2.5
    var clutterDiameter: ClosedRange<Float> = 0.01...0.12
    /// Additional hand-placed targets.
    var extraTargets: [SimTarget] = []
    var includeGridCapsules = true

    // Detector model
    var detectionProbability: Float = 0.85
    var distractorDetectionProbability: Float = 0.6
    var pixelNoise: Float = 1.5
    var sizeNoise: Float = 0.15
    var focalPixels: Float = 1450
    var halfFovX: Float = 0.58
    var halfFovY: Float = 0.46

    // Operator path: lateral sweeps in front of the face
    var standoff: Float = 1.2
    var sweepHalfWidth: Float = 1.3
    var walkSpeed: Float = 0.35
    /// Time windows (s) during which the camera is turned away from the face.
    var lookAway: [ClosedRange<Float>] = []
    /// ARKit pose drift accumulated along the path (m per m walked).
    var driftPerMeter: Float = 0

    // App settings
    var parameters = ReconstructionParameters()
    var assumedCapsuleDiameter: Float = 0.030
    var sizeTolerance: Float = 0.60
}

struct ScanReport: CustomStringConvertible {
    var scenario: String
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
    var observations = 0

    var recall: Float {
        capsules == 0 ? 1 : Float(matchedCapsules) / Float(capsules)
    }

    var description: String {
        String(
            format: "capsules=%d confirmed=%d recall=%.0f%% duplicates=%d inaccurate=%d false=%d rms=%.1fmm max=%.1fmm obs=%d",
            capsules, confirmed, recall * 100, duplicates, inaccurate, falseConfirmed,
            rmsErrorMm, maxErrorMm, observations
        )
    }

    /// GitHub Actions annotation, visible on the workflow run page.
    func annotate() {
        print("::notice title=Scenario \(scenario)::\(description)")
    }
}

enum ScanSimulator {
    static let matchRadius: Float = 0.03
    static let nearRadius: Float = 0.10

    /// Face frame placed off-axis in the ARKit world on purpose.
    static func faceTransform() -> simd_float4x4 {
        var transform = simd_float4x4(simd_quatf(angle: 25 * Float.pi / 180, axis: SIMD3<Float>(0, 1, 0)))
        transform.columns.3 = SIMD4<Float>(0.4, 1.1, -0.7, 1)
        return transform
    }

    static func makeTargets(_ s: ScanScenario, rng: inout SplitMix64) -> [SimTarget] {
        var targets: [SimTarget] = []
        let usable = s.faceSize * 0.85

        func grid(z: Float, kind: SimTargetKind, shift: SIMD2<Float>) {
            for column in 0..<s.capsuleColumns {
                for row in 0..<s.capsuleRows {
                    let u = s.capsuleColumns > 1 ? Float(column) / Float(s.capsuleColumns - 1) - 0.5 : 0
                    let v = s.capsuleRows > 1 ? Float(row) / Float(s.capsuleRows - 1) - 0.5 : 0
                    let x = u * usable + shift.x + rng.uniform(-s.capsuleJitter...s.capsuleJitter)
                    let y = v * usable + shift.y + rng.uniform(-s.capsuleJitter...s.capsuleJitter)
                    targets.append(SimTarget(kind: kind, local: SIMD3<Float>(x, y, z), diameter: s.capsuleDiameter))
                }
            }
        }

        if s.includeGridCapsules {
            grid(z: s.planeOffset, kind: .capsule, shift: .zero)

            let originals = targets
            for index in 0..<min(s.closePairs, originals.count) {
                let base = originals[(index * 7) % originals.count]
                let angle = rng.uniform(0...(2 * Float.pi))
                let offset = SIMD3<Float>(cos(angle), sin(angle), 0) * s.closePairDistance
                targets.append(SimTarget(kind: .capsule, local: base.local + offset, diameter: s.capsuleDiameter))
            }
        }

        if s.backFace {
            grid(z: s.planeOffset - s.backFaceDepth, kind: .backCapsule, shift: SIMD2<Float>(0.11, -0.07))
        }

        for _ in 0..<s.clutterCount {
            let local = SIMD3<Float>(
                rng.uniform(-s.clutterSpread...s.clutterSpread),
                rng.uniform(-s.clutterSpread...s.clutterSpread),
                s.planeOffset - rng.uniform(s.clutterDepth)
            )
            targets.append(SimTarget(kind: .clutter, local: local, diameter: rng.uniform(s.clutterDiameter)))
        }

        return targets + s.extraTargets
    }

    /// Camera position and aim point in the face frame at time t.
    static func cameraPath(_ s: ScanScenario, time t: Float) -> (position: SIMD3<Float>, aim: SIMD3<Float>) {
        let hw = s.sweepHalfWidth
        let period = 4 * hw / s.walkSpeed
        let phase = t.truncatingRemainder(dividingBy: period) / period
        let x = phase < 0.5 ? -hw + 4 * hw * phase : 3 * hw - 4 * hw * phase
        let y = 0.55 * sin(2 * Float.pi * t / 23)
        let z = s.planeOffset + s.standoff + 0.12 * sin(2 * Float.pi * t / 9)

        let position = SIMD3<Float>(x, y, z)
        let aim = SIMD3<Float>(0.75 * x + 0.25 * sin(2 * Float.pi * t / 7), 0.7 * y, s.planeOffset)
        return (position, aim)
    }

    static func run(_ s: ScanScenario) -> (report: ScanReport, reconstructor: TrackReconstructor) {
        var rng = SplitMix64(seed: s.seed)
        let faceTransform = faceTransform()
        let face = FaceGeometry(
            transform: faceTransform,
            width: s.faceSize,
            height: s.faceSize,
            planeOffset: s.planeOffset
        )
        let targets = makeTargets(s, rng: &rng)
        let targetsWorld = targets.map { faceTransform.transformPoint($0.local) }

        var reconstructor = TrackReconstructor()
        reconstructor.parameters = s.parameters

        let driftDirection = simd_normalize(SIMD3<Float>(1, 0.5, -0.3))
        var pathLength: Float = 0
        var previousPosition: SIMD3<Float>?
        var frame = 0
        var totalObservations = 0

        var t: Float = 0
        while t < s.duration {
            frame += s.framesPerTick

            let pose = cameraPath(s, time: t)
            let position = faceTransform.transformPoint(pose.position)
            if let previousPosition {
                pathLength += simd_distance(previousPosition, position)
            }
            previousPosition = position

            let lookingAway = s.lookAway.contains { $0.contains(t) }
            var aim = faceTransform.transformPoint(pose.aim)
            if lookingAway {
                aim = position + (position - aim)
            }

            let forward = simd_normalize(aim - position)
            let right = simd_normalize(simd_cross(forward, SIMD3<Float>(0, 1, 0)))
            let up = simd_cross(right, forward)
            let reportedOrigin = position + driftDirection * (s.driftPerMeter * pathLength)

            var detections: [(observation: DetectionObservation, diameterPixels: Float)] = []

            for (index, target) in targets.enumerated() {
                let v = targetsWorld[index] - position
                let depth = simd_dot(v, forward)
                guard depth > 0.15 else { continue }
                guard
                    abs(atan2(simd_dot(v, right), depth)) < s.halfFovX,
                    abs(atan2(simd_dot(v, up), depth)) < s.halfFovY
                else { continue }

                let probability = target.kind == .capsule ? s.detectionProbability : s.distractorDetectionProbability
                guard rng.chance(probability) else { continue }

                let sigma = s.pixelNoise / s.focalPixels
                let direction = simd_normalize(
                    simd_normalize(v) +
                    right * rng.gaussian(sigma: sigma) +
                    up * rng.gaussian(sigma: sigma)
                )
                let diameterPixels = s.focalPixels * target.diameter / depth * max(0.2, 1 + rng.gaussian(sigma: s.sizeNoise))

                // Same chain as ARScannerView.consume: plane intersection, then size filter.
                guard let nominal = face.nominalIntersection(origin: reportedOrigin, direction: direction) else { continue }
                let nominalDepth = simd_dot(nominal.world - reportedOrigin, forward)
                guard CapsuleSizeFilter.passes(
                    observedDiameterPixels: diameterPixels,
                    physicalDiameter: s.assumedCapsuleDiameter,
                    depth: nominalDepth,
                    focalPixels: s.focalPixels,
                    tolerance: s.sizeTolerance
                ) else { continue }

                let observation = DetectionObservation(
                    kind: .white,
                    ray: RayObservation(origin: reportedOrigin, direction: direction),
                    localXY: SIMD2<Float>(nominal.local.x, nominal.local.y)
                )
                detections.append((observation, diameterPixels))
            }

            // CapsuleDetector returns the blobs sorted by decreasing size.
            detections.sort { $0.diameterPixels > $1.diameterPixels }
            totalObservations += detections.count
            reconstructor.update(with: detections.map { $0.observation }, frame: frame, face: face)

            t += s.tickInterval
        }

        var report = evaluate(reconstructor, targets: targets, face: face, scenario: s.name)
        report.observations = totalObservations
        return (report, reconstructor)
    }

    static func evaluate(
        _ reconstructor: TrackReconstructor,
        targets: [SimTarget],
        face: FaceGeometry,
        scenario: String
    ) -> ScanReport {
        let capsules = targets.filter { $0.kind == .capsule }.map(\.local)
        let worldToFace = simd_inverse(face.transform)

        var report = ScanReport(scenario: scenario)
        report.capsules = capsules.count

        var matchesPerCapsule = [Int](repeating: 0, count: capsules.count)
        var bestError = [Float](repeating: .greatestFiniteMagnitude, count: capsules.count)

        for track in reconstructor.tracks where track.state == .confirmed && track.kind == .white {
            guard let world = track.worldPoint else { continue }
            report.confirmed += 1

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
                report.inaccurate += 1
            } else {
                report.falseConfirmed += 1
            }
        }

        var sumSquared: Float = 0
        for index in capsules.indices where matchesPerCapsule[index] > 0 {
            report.matchedCapsules += 1
            report.duplicates += matchesPerCapsule[index] - 1
            sumSquared += bestError[index] * bestError[index]
            report.maxErrorMm = max(report.maxErrorMm, bestError[index] * 1000)
        }
        if report.matchedCapsules > 0 {
            report.rmsErrorMm = sqrt(sumSquared / Float(report.matchedCapsules)) * 1000
        }

        return report
    }
}
