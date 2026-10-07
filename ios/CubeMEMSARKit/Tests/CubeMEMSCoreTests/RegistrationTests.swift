import XCTest
import simd
@testable import CubeMEMSCore

final class RegistrationTests: XCTestCase {
    /// 96 microphones: 12 columns × 8 rows, numbered like the app (n° 1 bottom right).
    private func faceMicrophones() -> [NumberedMicrophone] {
        var tracks: [MicroTrack] = []
        for column in 0..<12 {
            for row in 0..<8 {
                let local = SIMD3<Float>(
                    0.85 - 1.7 * Float(column) / 11,
                    -0.8 + 1.6 * Float(row) / 7,
                    0.03 + 0.002 * Float((column + row) % 3)
                )
                var track = MicroTrack(kind: .white, rays: [], localXY: SIMD2<Float>(local.x, local.y), lastFrame: 0, seenThisFrame: false)
                track.localPoint = local
                track.state = .confirmed
                tracks.append(track)
            }
        }
        return MicrophoneNumbering.number(tracks.shuffled(), columnGap: 0.08)
    }

    /// Real frame: face plane becomes Z = 1.455 m, rotated, like a cube face in GEO_256.
    private let truth: RigidTransform = {
        let q = simd_quatd(angle: 1.3 * .pi / 180, axis: simd_normalize(SIMD3<Double>(0.2, 0.1, 1)))
            * simd_quatd(angle: .pi / 2, axis: SIMD3<Double>(1, 0, 0))
        return RigidTransform(rotation: simd_double3x3(q), translation: SIMD3<Double>(0.1, 1.0, 1.455))
    }()

    private func references(_ channels: [Int], from microphones: [NumberedMicrophone]) -> [Int: SIMD3<Double>] {
        var result: [Int: SIMD3<Double>] = [:]
        for channel in channels {
            let microphone = microphones.first { $0.number == channel }!
            result[channel] = SIMD3<Double>(truth.apply(microphone.position))
        }
        return result
    }

    func testFourCornersRecoverTheTransform() throws {
        let microphones = faceMicrophones()
        XCTAssertEqual(microphones.first?.column, 1)
        XCTAssertEqual(microphones.count, 96)

        let result = RigidRegistration.register(microphones: microphones, references: references([1, 8, 89, 96], from: microphones))
        let registration = try result.get()

        XCTAssertFalse(registration.translationOnly)
        XCTAssertLessThan(registration.rmsMm, 0.01)
        for microphone in microphones {
            let expected = truth.apply(microphone.position)
            XCTAssertLessThan(simd_distance(registration.transform.apply(microphone.position), expected), 1e-5)
        }
    }

    func testNonCornerChannelsAlsoWork() throws {
        let microphones = faceMicrophones()
        let registration = try RigidRegistration.register(
            microphones: microphones,
            references: references([1, 8, 88, 96], from: microphones)
        ).get()
        XCTAssertLessThan(registration.rmsMm, 0.01)
    }

    func testRefusedCases() {
        let microphones = faceMicrophones()

        XCTAssertEqual(errorOf(RigidRegistration.register(microphones: microphones, references: [:])), .noReference)
        XCTAssertEqual(errorOf(RigidRegistration.register(microphones: microphones, references: references([1, 96], from: microphones))), .twoReferences)
        // 1, 2, 3 are in the same column: collinear.
        XCTAssertEqual(errorOf(RigidRegistration.register(microphones: microphones, references: references([1, 2, 3], from: microphones))), .collinear)

        var withMissing = references([1, 8, 96], from: microphones)
        withMissing[150] = SIMD3<Double>(0, 0, 0)
        XCTAssertEqual(errorOf(RigidRegistration.register(microphones: microphones, references: withMissing)), .missingChannels([150]))
    }

    func testSingleReferenceIsTranslationOnly() throws {
        let microphones = faceMicrophones()
        let registration = try RigidRegistration.register(
            microphones: microphones,
            references: [1: SIMD3<Double>(1, 2, 3)]
        ).get()
        XCTAssertTrue(registration.translationOnly)
        XCTAssertEqual(registration.transform.rotationDegrees, 0, accuracy: 1e-9)
        XCTAssertLessThan(simd_distance(SIMD3<Double>(registration.transform.apply(microphones[0].position)), SIMD3<Double>(1, 2, 3)), 1e-6)
    }

    func testExportInRealFrame() throws {
        let microphones = faceMicrophones()
        let transform = try RigidRegistration.register(
            microphones: microphones,
            references: references([1, 8, 89, 96], from: microphones)
        ).get().transform

        let geometry = MicrophoneExport.geometryCSV(microphones, transform: transform).split(separator: "\n")
        XCTAssertEqual(geometry.count, 97)
        let first = geometry[1].split(separator: ";").map { Double($0)! }
        let expected = truth.apply(microphones[0].position)
        XCTAssertEqual(first[0], Double(expected.x), accuracy: 1e-4)
        XCTAssertEqual(first[1], Double(expected.y), accuracy: 1e-4)
        XCTAssertEqual(first[2], Double(expected.z), accuracy: 1e-4)

        let header = MicrophoneExport.detailedCSV(microphones, transform: transform).split(separator: "\n").first
        XCTAssertEqual(header, "num;colonne;rang;X_m;Y_m;Z_m;incertitude_mm;rayons;residu_mm;X_reel_m;Y_reel_m;Z_reel_m")
    }

    private func errorOf(_ result: Result<ReferenceRegistration, ReferenceRegistrationError>) -> ReferenceRegistrationError? {
        if case .failure(let error) = result { return error }
        return nil
    }
}
