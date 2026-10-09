import Foundation
import simd
import XCTest
@testable import CubeMEMSCore

final class GridNumberingTests: XCTestCase {
    private func confirmedTrack(_ local: SIMD3<Float>, uncertainty: Float = 0.003) -> MicroTrack {
        var track = MicroTrack(kind: .white, rays: [], localXY: SIMD2<Float>(local.x, local.y), lastFrame: 0, seenThisFrame: false)
        track.localPoint = local
        track.state = .confirmed
        track.uncertainty = uncertainty
        return track
    }

    /// 12 × 8 grid, irregular by ~1 cm, 40 % missing and the two leftmost columns never scanned:
    /// every found microphone must get the number of its own slot (holes, not shifts).
    func testIrregularPartialGridKeepsSlotNumbers() {
        var generator = SplitMix64(seed: 3)
        var tracks: [MicroTrack] = []
        var expected: [Int: Int] = [:]   // track index -> slot
        for column in 0..<12 {
            for row in 0..<8 where column < 10 && !generator.chance(0.4) {
                let x = 0.8 - 1.6 * Float(column) / 11 + generator.gaussian(sigma: 0.012)
                let y = -0.75 + 1.4 * Float(row) / 7 + generator.gaussian(sigma: 0.012)
                expected[tracks.count] = column * 8 + row + 1
                tracks.append(confirmedTrack(SIMD3<Float>(x, y, -0.08)))
            }
        }

        let result = GridNumbering.number(tracks, layout: GridLayout(), faceWidth: 1.95, faceHeight: 1.83)

        XCTAssertEqual(result.unassigned, 0)
        XCTAssertEqual(result.microphones.count, tracks.count)
        for microphone in result.microphones {
            XCTAssertEqual(microphone.number, expected[microphone.trackIndex], "track \(microphone.trackIndex)")
            XCTAssertEqual(microphone.column, (microphone.number - 1) / 8 + 1)
            XCTAssertEqual(microphone.row, (microphone.number - 1) % 8 + 1)
        }
        XCTAssertEqual(result.missing.count, 96 - tracks.count)
        XCTAssertTrue(result.missing.contains(96), "top-left slot of a never scanned column")
    }

    /// Column gaps from 11 to 18 cm and row gaps from 15 to 25 cm (unequal spacing), 30 % missing.
    func testUnequalSpacingKeepsSlotNumbers() {
        let columnGaps: [Float] = [0.13, 0.11, 0.16, 0.18, 0.12, 0.15, 0.14, 0.17, 0.12, 0.16, 0.13]
        let rowGaps: [Float] = [0.18, 0.25, 0.15, 0.22, 0.19, 0.24, 0.16]
        var columnX: [Float] = [0.8]
        for gap in columnGaps { columnX.append(columnX.last! - gap) }      // column 0 = rightmost
        var rowY: [Float] = [-0.75]
        for gap in rowGaps { rowY.append(rowY.last! + gap) }               // row 0 = bottom

        var generator = SplitMix64(seed: 11)
        var tracks: [MicroTrack] = []
        var expected: [Int: Int] = [:]
        for column in 0..<12 {
            for row in 0..<8 {
                if generator.chance(0.3) { continue }
                let x = columnX[column] + generator.gaussian(sigma: 0.01)
                let y = rowY[row] + generator.gaussian(sigma: 0.012)
                expected[tracks.count] = column * 8 + row + 1
                tracks.append(confirmedTrack(SIMD3<Float>(x, y, -0.08)))
            }
        }

        let result = GridNumbering.number(tracks, layout: GridLayout(), faceWidth: 1.95, faceHeight: 1.83)
        XCTAssertEqual(result.unassigned, 0)
        XCTAssertFalse(result.ambiguous)
        XCTAssertEqual(result.microphones.count, tracks.count)
        for microphone in result.microphones {
            XCTAssertEqual(microphone.number, expected[microphone.trackIndex], "track \(microphone.trackIndex)")
        }
    }

    /// The 35 microphones reconstructed from the real recording of 2026-10-08 (PC replay):
    /// same slots as the Python reference tools/replay/grille.py.
    func testRealScanMatchesReference() throws {
        struct Fixture: Decodable {
            var faceWidth: Float
            var faceHeight: Float
            var points: [[Float]]
            var uncertainties: [Float]
            var expectedSlots: [String: Int]
        }
        let url = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures", withExtension: nil))
            .appendingPathComponent("grid_scan_20261008.json")
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))

        let tracks = zip(fixture.points, fixture.uncertainties).map {
            confirmedTrack(SIMD3<Float>($0[0], $0[1], $0[2]), uncertainty: $1)
        }
        let result = GridNumbering.number(tracks, layout: GridLayout(), faceWidth: fixture.faceWidth, faceHeight: fixture.faceHeight)

        let slots = Dictionary(uniqueKeysWithValues: result.microphones.map { ("\($0.number)", $0.trackIndex) })
        XCTAssertEqual(slots, fixture.expectedSlots)
    }

    func testGeometryCSVKeepsHolesForMissingSlots() {
        let microphones = [
            NumberedMicrophone(number: 1, trackIndex: 0, column: 1, row: 1, position: SIMD3<Float>(0.5, -0.5, -0.08), uncertainty: 0.003, rays: 9, residual: 0.002),
            NumberedMicrophone(number: 3, trackIndex: 1, column: 1, row: 3, position: SIMD3<Float>(0.5, 0, -0.08), uncertainty: 0.003, rays: 9, residual: 0.002)
        ]
        let lines = MicrophoneExport.geometryCSV(microphones, slotCount: 4).split(separator: "\n").map(String.init)
        XCTAssertEqual(lines, ["X;Y;Z", "0.50000;-0.50000;-0.08000", "nan;nan;nan", "0.50000;0.00000;-0.08000", "nan;nan;nan"])
    }
}
