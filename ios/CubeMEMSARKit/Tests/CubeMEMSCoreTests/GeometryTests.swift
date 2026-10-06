import XCTest
import simd
@testable import CubeMEMSCore

/// Exact-geometry checks of the reconstruction core. These must always pass.
final class GeometryTests: XCTestCase {
    private let face = FaceGeometry(
        transform: ScanSimulator.faceTransform(),
        width: 2,
        height: 2,
        planeOffset: 0.03
    )

    private func world(_ local: SIMD3<Float>) -> SIMD3<Float> {
        face.transform.transformPoint(local)
    }

    private func ray(from origin: SIMD3<Float>, to point: SIMD3<Float>) -> RayObservation {
        RayObservation(origin: origin, direction: simd_normalize(point - origin))
    }

    /// Observations of one face-local point from a lateral camera walk (8 cm steps, 1.2 m away).
    private func feedLateralWalk(
        of localPoint: SIMD3<Float>,
        steps: Int,
        into reconstructor: inout TrackReconstructor
    ) {
        for step in 0..<steps {
            let x = -0.4 + 0.08 * Float(step)
            let origin = world(SIMD3<Float>(x, 0.1, 1.2))
            let observedRay = ray(from: origin, to: world(localPoint))
            guard let nominal = face.nominalIntersection(origin: observedRay.origin, direction: observedRay.direction) else {
                XCTFail("ray misses the face")
                return
            }
            let observation = DetectionObservation(
                kind: .white,
                ray: observedRay,
                localXY: SIMD2<Float>(nominal.local.x, nominal.local.y)
            )
            reconstructor.update(with: [observation], frame: step * 12, face: face)
        }
    }

    func testTriangulationRecoversPointFromNoiseFreeRays() throws {
        let point = SIMD3<Float>(0.3, 1.2, -0.5)
        let origins: [SIMD3<Float>] = [
            SIMD3<Float>(-0.4, 1.0, 0.8),
            SIMD3<Float>(0.0, 1.3, 0.9),
            SIMD3<Float>(0.5, 1.1, 0.7),
            SIMD3<Float>(0.9, 1.4, 0.6)
        ]
        let result = try XCTUnwrap(Triangulation.triangulate(origins.map { ray(from: $0, to: point) }))

        XCTAssertLessThan(simd_distance(result.point, point), 5e-4)
        XCTAssertLessThan(result.residual, 5e-4)
    }

    func testTriangulationRejectsDegenerateRays() {
        let direction = simd_normalize(SIMD3<Float>(0.1, 0, -1))
        let parallel = [
            RayObservation(origin: SIMD3<Float>(0, 1, 1), direction: direction),
            RayObservation(origin: SIMD3<Float>(0.3, 1, 1), direction: direction),
            RayObservation(origin: SIMD3<Float>(0.6, 1, 1), direction: direction)
        ]

        XCTAssertNil(Triangulation.triangulate(parallel))
        XCTAssertNil(Triangulation.triangulate(Array(parallel.prefix(1))))
    }

    func testMaximumBaseline() {
        let rays = [
            RayObservation(origin: SIMD3<Float>(0, 0, 0), direction: SIMD3<Float>(0, 0, -1)),
            RayObservation(origin: SIMD3<Float>(0.3, 0, 0), direction: SIMD3<Float>(0, 0, -1)),
            RayObservation(origin: SIMD3<Float>(0, 0.4, 0), direction: SIMD3<Float>(0, 0, -1))
        ]

        XCTAssertEqual(Triangulation.maximumBaseline(rays), 0.5, accuracy: 1e-5)
    }

    func testNominalIntersectionHitsMicrophonePlane() throws {
        let target = SIMD3<Float>(0.2, -0.4, 0.03)
        let origin = world(SIMD3<Float>(0.5, 0.1, 1.2))
        let direction = simd_normalize(world(target) - origin)

        let hit = try XCTUnwrap(face.nominalIntersection(origin: origin, direction: direction))
        XCTAssertLessThan(simd_distance(hit.local, target), 1e-4)
        XCTAssertLessThan(face.planeDistance(hit.world), 1e-4)

        // Pointing away from the face.
        XCTAssertNil(face.nominalIntersection(origin: origin, direction: -direction))

        // Outside the face rectangle + 10 cm margin.
        let outside = simd_normalize(world(SIMD3<Float>(1.5, 0, 0.03)) - origin)
        XCTAssertNil(face.nominalIntersection(origin: origin, direction: outside))
    }

    func testSizeFilterBounds() {
        let expected = CapsuleSizeFilter.expectedDiameterPixels(physicalDiameter: 0.03, depth: 1.2, focalPixels: 1450)
        XCTAssertEqual(expected, 36.25, accuracy: 1e-3)

        func passes(_ pixels: Float, depth: Float = 1.2) -> Bool {
            CapsuleSizeFilter.passes(
                observedDiameterPixels: pixels,
                physicalDiameter: 0.03,
                depth: depth,
                focalPixels: 1450,
                tolerance: 0.6
            )
        }

        XCTAssertTrue(passes(expected))
        XCTAssertTrue(passes(expected * 1.5))
        XCTAssertFalse(passes(expected * 1.7))
        XCTAssertFalse(passes(expected * 0.35))
        XCTAssertFalse(passes(expected, depth: 0.04))
    }

    func testSingleCapsuleIsConfirmedAccurately() throws {
        let capsule = SIMD3<Float>(0.1, 0.2, 0.03)
        var reconstructor = TrackReconstructor()
        feedLateralWalk(of: capsule, steps: 10, into: &reconstructor)

        XCTAssertEqual(reconstructor.tracks.count, 1)
        let track = try XCTUnwrap(reconstructor.tracks.first)
        XCTAssertEqual(track.state, .confirmed)
        let point = try XCTUnwrap(track.worldPoint)
        XCTAssertLessThan(simd_distance(point, world(capsule)), 1e-3)
    }

    func testObjectHalfMeterBehindFaceIsNeverConfirmed() {
        let behind = SIMD3<Float>(0.1, 0.2, 0.03 - 0.5)
        var reconstructor = TrackReconstructor()
        feedLateralWalk(of: behind, steps: 12, into: &reconstructor)

        XCTAssertEqual(reconstructor.confirmedCount, 0)
        XCTAssertGreaterThan(reconstructor.rejectedCount, 0)
    }

    /// The virtual-antenna detector must cast rays that hit the true target (no pixel noise),
    /// and ignore targets behind the camera or outside the image.
    func testVirtualAntennaRaysPointAtTargets() throws {
        let scenario = ScanScenario(name: "projection")
        let antenna = VirtualAntenna(targets: [
            VirtualTarget(kind: .capsule, local: SIMD3<Float>(0.2, -0.1, 0.03), diameter: 0.03),
            VirtualTarget(kind: .clutter, local: SIMD3<Float>(0, 0, 3.0), diameter: 0.05),
            VirtualTarget(kind: .capsule, local: SIMD3<Float>(6, 0, 0.03), diameter: 0.03)
        ])
        let position = world(SIMD3<Float>(0.3, 0.1, 1.2))
        let camera = ScanSimulator.makeCamera(scenario, position: position, aim: world(SIMD3<Float>(0, 0, 0)))
        var model = DetectorModel()
        model.detectionProbability = 1
        model.distractorDetectionProbability = 1
        model.pixelNoise = 0
        model.sizeNoise = 0
        var rng = SplitMix64(seed: 1)

        let detections = antenna.detections(face: face, camera: camera, model: model, rng: &rng)
        XCTAssertEqual(detections.count, 1)
        let detection = try XCTUnwrap(detections.first)
        let target = world(SIMD3<Float>(0.2, -0.1, 0.03))
        let toTarget = target - detection.origin
        let perpendicular = toTarget - detection.direction * simd_dot(toTarget, detection.direction)
        XCTAssertLessThan(simd_length(perpendicular), 1e-4)

        let expectedPixels = scenario.focalPixels * 0.03 / simd_dot(toTarget, -camera.transform.zAxis)
        XCTAssertEqual(detection.diameterPixels, expectedPixels, accuracy: 0.05)
    }

    func testWorldCorrectionMovesTracksRigidly() throws {
        let capsule = SIMD3<Float>(-0.2, 0.3, 0.03)
        var reconstructor = TrackReconstructor()
        feedLateralWalk(of: capsule, steps: 10, into: &reconstructor)
        let before = try XCTUnwrap(reconstructor.tracks.first?.worldPoint)

        var delta = simd_float4x4(simd_quatf(angle: 4 * Float.pi / 180, axis: simd_normalize(SIMD3<Float>(1, 1, 0))))
        delta.columns.3 = SIMD4<Float>(0.02, -0.01, 0.03, 1)
        reconstructor.applyWorldCorrection(delta)

        let after = try XCTUnwrap(reconstructor.tracks.first?.worldPoint)
        XCTAssertLessThan(simd_distance(after, delta.transformPoint(before)), 1e-4)

        let retriangulated = try XCTUnwrap(Triangulation.triangulate(reconstructor.tracks[0].rays))
        XCTAssertLessThan(simd_distance(retriangulated.point, after), 1e-3)
    }
}
