import Foundation
import simd
@testable import CubeMEMSCore

// Synthetic walk-around scan of one cube face. The operator path replaces ARKit, and
// VirtualAntenna replaces the real antenna + CapsuleDetector (same code as the app's
// "antenne virtuelle" mode). Detections go through the same chain as
// ARScannerView.consume: plane intersection, size filter, then TrackReconstructor.

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
    var capsuleDiameter: Float = 0.030
    /// Extra capsules placed 6 cm away from existing ones.
    var closePairs = 0

    // Distractors
    var backFace = false
    var clutterCount = 0

    // Detector and camera (iPhone wide camera, 1920 × 1440 class)
    var detector = DetectorModel()
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
    var sizeTolerance: Float = 0.30
}

struct ScanReport: CustomStringConvertible {
    var scenario: String
    var score: ScanScore
    var observations = 0

    var falseConfirmed: Int { score.falseConfirmed }
    var inaccurate: Int { score.inaccurate }
    var duplicates: Int { score.duplicates }
    var recall: Float { score.recall }
    var rmsErrorMm: Float { score.rmsErrorMm }

    var description: String {
        "\(score) obs=\(observations)"
    }

    /// GitHub Actions annotation, visible on the workflow run page.
    func annotate() {
        print("::notice title=Scenario \(scenario)::\(description)")
    }
}

enum ScanSimulator {
    /// Face frame placed off-axis in the ARKit world on purpose.
    static func faceTransform() -> simd_float4x4 {
        var transform = simd_float4x4(simd_quatf(angle: 25 * Float.pi / 180, axis: SIMD3<Float>(0, 1, 0)))
        transform.columns.3 = SIMD4<Float>(0.4, 1.1, -0.7, 1)
        return transform
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

    /// ARKit-style camera at `position` looking at `aim` (world), gravity-up.
    static func makeCamera(_ s: ScanScenario, position: SIMD3<Float>, aim: SIMD3<Float>) -> PinholeCamera {
        let forward = simd_normalize(aim - position)
        let right = simd_normalize(simd_cross(forward, SIMD3<Float>(0, 1, 0)))
        let up = simd_cross(right, forward)

        var transform = matrix_identity_float4x4
        transform.columns.0 = SIMD4<Float>(right, 0)
        transform.columns.1 = SIMD4<Float>(up, 0)
        transform.columns.2 = SIMD4<Float>(-forward, 0)
        transform.columns.3 = SIMD4<Float>(position, 1)

        let f = s.focalPixels
        let cx = f * tan(s.halfFovX)
        let cy = f * tan(s.halfFovY)
        let intrinsics = simd_float3x3(columns: (
            SIMD3<Float>(f, 0, 0),
            SIMD3<Float>(0, f, 0),
            SIMD3<Float>(cx, cy, 1)
        ))

        return PinholeCamera(transform: transform, intrinsics: intrinsics, imageSize: SIMD2<Float>(2 * cx, 2 * cy))
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
        let antenna = VirtualAntenna.make(
            faceSize: s.faceSize,
            planeOffset: s.planeOffset,
            capsuleDiameter: s.capsuleDiameter,
            closePairs: s.closePairs,
            backFace: s.backFace,
            clutterCount: s.clutterCount,
            rng: &rng
        )

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

            var aim = faceTransform.transformPoint(pose.aim)
            if s.lookAway.contains(where: { $0.contains(t) }) {
                aim = position + (position - aim)
            }

            let camera = makeCamera(s, position: position, aim: aim)
            let forward = -camera.transform.zAxis
            let drift = driftDirection * (s.driftPerMeter * pathLength)

            var observations: [DetectionObservation] = []
            for detection in antenna.detections(face: face, camera: camera, model: s.detector, rng: &rng) {
                // ARKit reports a drifted camera position; the pixel direction is unchanged.
                let origin = detection.origin + drift

                // Same chain as ARScannerView.consume: plane intersection, then size filter.
                guard let nominal = face.nominalIntersection(origin: origin, direction: detection.direction) else { continue }
                guard CapsuleSizeFilter.passes(
                    observedDiameterPixels: detection.diameterPixels,
                    physicalDiameter: s.assumedCapsuleDiameter,
                    depth: simd_dot(nominal.world - origin, forward),
                    focalPixels: s.focalPixels,
                    tolerance: s.sizeTolerance
                ) else { continue }

                observations.append(
                    DetectionObservation(
                        kind: .white,
                        ray: RayObservation(origin: origin, direction: detection.direction),
                        localXY: SIMD2<Float>(nominal.local.x, nominal.local.y)
                    )
                )
            }

            totalObservations += observations.count
            reconstructor.update(with: observations, frame: frame, face: face)

            t += s.tickInterval
        }

        let score = ReconstructionScorer.score(
            tracks: reconstructor.tracks,
            capsules: antenna.capsulePositions,
            face: face
        )
        return (ScanReport(scenario: s.name, score: score, observations: totalObservations), reconstructor)
    }
}
