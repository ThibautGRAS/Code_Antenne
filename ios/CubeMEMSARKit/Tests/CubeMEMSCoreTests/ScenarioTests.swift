import XCTest
@testable import CubeMEMSCore

/// Simulated walk-around scans with the app's current default settings.
/// The assertions state the TARGET behavior (CLAUDE.md priorities): no false or duplicate
/// green microphones, good recall, millimetric accuracy.
/// Scenarios that still fail are wrapped in XCTExpectFailure (strict): once a fix makes one
/// pass, CI turns red to remind us to remove its `knownIssue`.
final class ScenarioTests: XCTestCase {
    private func run(_ scenario: ScanScenario) -> ScanReport {
        let report = ScanSimulator.run(scenario).report
        report.annotate()
        print("[\(scenario.name)] \(report)")
        return report
    }

    private func assertTargets(
        _ report: ScanReport,
        minRecall: Float = 0.9,
        maxRmsMm: Float = 10,
        knownIssue: String? = nil,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        if let knownIssue {
            XCTExpectFailure(knownIssue)
        }
        let summary = "\(report.scenario): \(report)"
        XCTAssertEqual(report.falseConfirmed, 0, "false green micros — \(summary)", file: file, line: line)
        XCTAssertEqual(report.inaccurate, 0, "inaccurate green micros — \(summary)", file: file, line: line)
        XCTAssertEqual(report.duplicates, 0, "duplicate green micros — \(summary)", file: file, line: line)
        XCTAssertGreaterThanOrEqual(report.recall, minRecall, "recall — \(summary)", file: file, line: line)
        XCTAssertLessThanOrEqual(report.rmsErrorMm, maxRmsMm, "accuracy — \(summary)", file: file, line: line)
    }

    /// Ideal room: only the capsules of the scanned face.
    func testCleanFace() {
        assertTargets(run(ScanScenario(name: "clean-face")), knownIssue: "duplicate greens when a capsule leaves the view > associationMaxFrameGap")
    }

    /// Anechoic room: opposite face visible through the net + white objects behind.
    func testAnechoicClutter() {
        var scenario = ScanScenario(name: "anechoic-clutter")
        scenario.backFace = true
        scenario.clutterCount = 80
        assertTargets(run(scenario), minRecall: 0.85, knownIssue: "duplicates + false greens from back face and clutter")
    }

    /// The operator turns away three times, then comes back on the same capsules.
    func testLeaveAndReturn() {
        var scenario = ScanScenario(name: "leave-and-return")
        scenario.lookAway = [15...18, 32...35, 48...51]
        assertTargets(run(scenario), knownIssue: "duplicate greens when a capsule leaves the view > associationMaxFrameGap")
    }

    /// Some capsules only 6 cm apart.
    func testCloseNeighbours() {
        var scenario = ScanScenario(name: "close-neighbours")
        scenario.closePairs = 10
        assertTargets(run(scenario), minRecall: 0.85, knownIssue: "duplicate greens when a capsule leaves the view > associationMaxFrameGap")
    }

    /// ARKit drift of 1 cm per meter walked, no ArUco recalibration.
    func testPoseDrift() {
        var scenario = ScanScenario(name: "pose-drift-1cm-per-m")
        scenario.driftPerMeter = 0.01
        assertTargets(run(scenario), maxRmsMm: 25, knownIssue: "drift: false greens and low recall")
    }

    /// Worst case: noisy, intermittent detector in the cluttered room.
    func testNoisyDetectorInClutter() {
        var scenario = ScanScenario(name: "noisy-detector-clutter")
        scenario.backFace = true
        scenario.clutterCount = 80
        scenario.detector.pixelNoise = 3
        scenario.detector.detectionProbability = 0.6
        scenario.detector.distractorDetectionProbability = 0.8
        assertTargets(run(scenario), minRecall: 0.7, maxRmsMm: 15, knownIssue: "duplicates + false greens")
    }
}
