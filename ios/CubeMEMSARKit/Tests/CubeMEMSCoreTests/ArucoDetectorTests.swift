import CoreGraphics
import Foundation
import ImageIO
import XCTest
@testable import CubeMEMSCore

/// Crops of a real recording on the antenna (2026-10-08): the Swift detector must match the
/// Python reference (tools/replay/aruco_detector.py), itself checked against OpenCV.
final class ArucoDetectorTests: XCTestCase {
    private struct Expected: Decodable {
        var ids: [Int]
        var id: Int?
        var center: [Double]?
    }

    private func fixturesURL() throws -> URL {
        try XCTUnwrap(Bundle.module.url(forResource: "Fixtures", withExtension: nil))
            .appendingPathComponent("aruco")
    }

    private func loadLuma(_ url: URL) throws -> LumaImage {
        let source = try XCTUnwrap(CGImageSourceCreateWithURL(url as CFURL, nil))
        let image = try XCTUnwrap(CGImageSourceCreateImageAtIndex(source, 0, nil))
        let width = image.width, height = image.height
        var pixels = [UInt8](repeating: 0, count: width * height)
        let drawn = pixels.withUnsafeMutableBytes { buffer -> Bool in
            guard let context = CGContext(
                data: buffer.baseAddress,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: width,
                space: CGColorSpaceCreateDeviceGray(),
                bitmapInfo: CGImageAlphaInfo.none.rawValue
            ) else { return false }
            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        XCTAssertTrue(drawn)
        return LumaImage(width: width, height: height, pixels: pixels)
    }

    func testRealMarkersMatchReference() throws {
        let folder = try fixturesURL()
        let data = try Data(contentsOf: folder.appendingPathComponent("expected.json"))
        let expected = try JSONDecoder().decode([String: Expected].self, from: data)
        XCTAssertEqual(expected.count, 5)

        for (name, case_) in expected.sorted(by: { $0.key < $1.key }) {
            let image = try loadLuma(folder.appendingPathComponent("\(name).png"))
            let detections = ArucoDetector.detect(image)
            XCTAssertEqual(detections.map { $0.id }, case_.ids, name)

            if let id = case_.id, let center = case_.center {
                let detection = try XCTUnwrap(detections.first { $0.id == id }, name)
                XCTAssertEqual(detection.center.x, center[0], accuracy: 1.0, name)
                XCTAssertEqual(detection.center.y, center[1], accuracy: 1.0, name)
                XCTAssertEqual(detection.corners.count, 4, name)
            }
        }
    }

    /// A synthetic marker drawn at a known place, rotated by 90° steps.
    func testSyntheticMarkerAllRotations() {
        for id in 0...3 {
            for rotation in 0..<4 {
                let size = 160, cell = 14, origin = 38
                var pixels = [UInt8](repeating: 230, count: size * size)
                var cells = ArucoDictionary.cells[id]!
                for _ in 0..<rotation {
                    cells = (0..<6).map { r in (0..<6).map { c in cells[5 - c][r] } }
                }
                for r in 0..<6 {
                    for c in 0..<6 where cells[r][c] == 0 {
                        for y in 0..<cell {
                            for x in 0..<cell {
                                pixels[(origin + r * cell + y) * size + origin + c * cell + x] = 20
                            }
                        }
                    }
                }
                let detections = ArucoDetector.detect(LumaImage(width: size, height: size, pixels: pixels))
                XCTAssertEqual(detections.map { $0.id }, [id], "id \(id) rotation \(rotation)")
                if let detection = detections.first {
                    let middle = Double(origin) + 3 * Double(cell) - 0.5
                    XCTAssertEqual(detection.center.x, middle, accuracy: 0.6)
                    XCTAssertEqual(detection.center.y, middle, accuracy: 0.6)
                }
            }
        }
    }
}
