import ARKit
import CoreGraphics
import ImageIO

enum ArucoReferenceFactory {
    // DICT_4X4_50 IDs 0...3, with the required 1-cell black border.
    private static let grids: [Int: [[UInt8]]] = [
        0: [
            [0,0,0,0,0,0],
            [0,1,0,1,1,0],
            [0,0,1,0,1,0],
            [0,0,0,1,1,0],
            [0,0,0,1,0,0],
            [0,0,0,0,0,0]
        ],
        1: [
            [0,0,0,0,0,0],
            [0,0,0,0,0,0],
            [0,1,1,1,1,0],
            [0,1,0,0,1,0],
            [0,1,0,1,0,0],
            [0,0,0,0,0,0]
        ],
        2: [
            [0,0,0,0,0,0],
            [0,0,0,1,1,0],
            [0,0,0,1,1,0],
            [0,0,0,1,0,0],
            [0,1,1,0,1,0],
            [0,0,0,0,0,0]
        ],
        3: [
            [0,0,0,0,0,0],
            [0,1,0,0,1,0],
            [0,1,0,0,1,0],
            [0,0,1,0,0,0],
            [0,0,1,1,0,0],
            [0,0,0,0,0,0]
        ]
    ]

    /// 6 × 6 cells (1 = white) including the black border, row 0 at the top.
    static func cells(id: Int) -> [[UInt8]]? {
        grids[id]
    }

    static func makeReferenceImages(markerWidthMeters: CGFloat) -> Set<ARReferenceImage> {
        var output = Set<ARReferenceImage>()

        for id in 0...3 {
            guard let image = makeMarkerCGImage(id: id) else { continue }
            let reference = ARReferenceImage(
                image,
                orientation: .up,
                physicalWidth: markerWidthMeters
            )
            reference.name = "aruco_\(id)"
            output.insert(reference)
        }

        return output
    }

    private static func makeMarkerCGImage(id: Int, pixels: Int = 600) -> CGImage? {
        guard let grid = grids[id], grid.count == 6 else { return nil }

        let colorSpace = CGColorSpaceCreateDeviceGray()
        guard let context = CGContext(
            data: nil,
            width: pixels,
            height: pixels,
            bitsPerComponent: 8,
            bytesPerRow: pixels,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.none.rawValue
        ) else { return nil }

        context.setFillColor(gray: 1, alpha: 1)
        context.fill(CGRect(x: 0, y: 0, width: pixels, height: pixels))

        let cell = CGFloat(pixels) / 6.0

        for row in 0..<6 {
            for col in 0..<6 {
                let isWhite = grid[row][col] == 1
                context.setFillColor(gray: isWhite ? 1 : 0, alpha: 1)

                // Core Graphics has its origin at bottom-left. Flip the row
                // so the generated image matches the printed ArUco orientation.
                let y = CGFloat(5 - row) * cell
                let rect = CGRect(
                    x: CGFloat(col) * cell,
                    y: y,
                    width: ceil(cell),
                    height: ceil(cell)
                )
                context.fill(rect)
            }
        }

        return context.makeImage()
    }
}
