import XCTest
import simd
@testable import CubeMEMSCore

final class ExportTests: XCTestCase {
    private func confirmedTrack(at local: SIMD3<Float>) -> MicroTrack {
        var track = MicroTrack(kind: .white, rays: [], localXY: SIMD2<Float>(local.x, local.y), lastFrame: 0, seenThisFrame: false)
        track.localPoint = local
        track.state = .confirmed
        track.uncertainty = 0.002
        track.residual = 0.001
        return track
    }

    /// 3 columns × 4 rows, slightly irregular, in shuffled order:
    /// n° 1 = bottom right, up the right column, then the next column to the left.
    func testNumberingStartsBottomRightAndClimbsColumnsRightToLeft() {
        var tracks: [MicroTrack] = []
        let columnsX: [Float] = [-0.30, 0.0, 0.30]
        let rowsY: [Float] = [-0.45, -0.15, 0.15, 0.45]
        for (c, x) in columnsX.enumerated() {
            for (r, y) in rowsY.enumerated() {
                let jitter = SIMD3<Float>(Float((c * 7 + r * 3) % 5) * 0.006 - 0.012, Float((c + r) % 3) * 0.01, 0.03)
                tracks.append(confirmedTrack(at: SIMD3<Float>(x, y, 0) + jitter))
            }
        }
        var provisional = confirmedTrack(at: SIMD3<Float>(0.5, 0.5, 0.03))
        provisional.state = .provisional
        tracks.append(provisional)
        tracks.reverse()

        let numbered = MicrophoneNumbering.number(tracks, columnGap: 0.08)

        XCTAssertEqual(numbered.count, 12, "only confirmed microphones are exported")
        XCTAssertEqual(numbered.map { $0.number }, Array(1...12))
        XCTAssertEqual(numbered.map { $0.column }, [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3])
        XCTAssertEqual(numbered.map { $0.row }, [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4])

        // First = rightmost column, lowest; 4 = rightmost, highest; 5 = middle column, lowest.
        XCTAssertEqual(numbered[0].position.x, 0.30, accuracy: 0.02)
        XCTAssertEqual(numbered[0].position.y, -0.45, accuracy: 0.03)
        XCTAssertEqual(numbered[3].position.y, 0.45, accuracy: 0.03)
        XCTAssertEqual(numbered[4].position.x, 0.0, accuracy: 0.02)
        XCTAssertEqual(numbered[4].position.y, -0.45, accuracy: 0.03)
        XCTAssertEqual(numbered[11].position.x, -0.30, accuracy: 0.02)
        XCTAssertEqual(numbered[11].position.y, 0.45, accuracy: 0.03)
    }

    func testCSVFormats() {
        let numbered = MicrophoneNumbering.number(
            [confirmedTrack(at: SIMD3<Float>(0.25, -0.5, 0.03)), confirmedTrack(at: SIMD3<Float>(0.25, 0.5, 0.03))],
            columnGap: 0.08
        )

        let geometry = MicrophoneExport.geometryCSV(numbered).split(separator: "\n").map(String.init)
        XCTAssertEqual(geometry, ["X;Y;Z", "0.25000;-0.50000;0.03000", "0.25000;0.50000;0.03000"])

        let details = MicrophoneExport.detailedCSV(numbered).split(separator: "\n").map(String.init)
        XCTAssertEqual(details.first, "num;colonne;rang;X_m;Y_m;Z_m;incertitude_mm;rayons;residu_mm")
        XCTAssertEqual(details[1], "1;1;1;0.25000;-0.50000;0.03000;2.0;0;1.0")
    }

    /// Full simulated scan: the 6 × 7 grid must come out as 6 columns of 7, n° 1 bottom right.
    func testNumberingOfSimulatedScan() throws {
        let result = ScanSimulator.run(ScanScenario(name: "numbering"))
        let numbered = MicrophoneNumbering.number(result.reconstructor.tracks, columnGap: 0.08)

        XCTAssertEqual(numbered.count, 42)
        XCTAssertEqual(Set(numbered.map { $0.column }).count, 6)
        for column in 1...6 {
            XCTAssertEqual(numbered.filter { $0.column == column }.count, 7, "column \(column)")
        }

        let first = try XCTUnwrap(numbered.first)
        XCTAssertEqual(first.position.x, numbered.map { $0.position.x }.max()!, accuracy: 0.07)
        XCTAssertEqual(first.position.y, numbered.map { $0.position.y }.min()!, accuracy: 0.07)
    }
}
