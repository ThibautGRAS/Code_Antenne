import Foundation
import simd

// Own ArUco detector (DICT_4X4_50, IDs 0–3), without ARKit or OpenCV.
// ARKit image anchors never recognized the printed markers on the real antenna (too small and
// too simple for its feature matching), whereas this detector finds them down to ~35 px.
// Validated against OpenCV on a real recording: 37/37 markers, center within ~1.3 px.
// Python reference: tools/replay/aruco_detector.py.

enum ArucoDictionary {
    /// 6 × 6 cells including the black border, 1 = white, row 0 at the top (printed orientation).
    static let cells: [Int: [[UInt8]]] = [
        0: [
            [0, 0, 0, 0, 0, 0],
            [0, 1, 0, 1, 1, 0],
            [0, 0, 1, 0, 1, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ],
        1: [
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 0],
            [0, 1, 0, 0, 1, 0],
            [0, 1, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ],
        2: [
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 0, 0],
            [0, 1, 1, 0, 1, 0],
            [0, 0, 0, 0, 0, 0]
        ],
        3: [
            [0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 1, 0],
            [0, 1, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 0, 0, 0, 0, 0]
        ]
    ]
}

/// 8-bit grayscale image, row-major, no padding.
struct LumaImage {
    let width: Int
    let height: Int
    var pixels: [UInt8]
}

struct ArucoMarkerDetection {
    var id: Int
    /// Pixel corners of the printed marker: top-left, top-right, bottom-right, bottom-left.
    /// Pixel (x, y) is centered on integer coordinates.
    var corners: [SIMD2<Double>]
    var center: SIMD2<Double>
}

enum ArucoDetector {
    struct Parameters {
        /// Adaptive threshold half-windows (px); results of all windows are merged.
        var radii: [Int] = [10, 15]
        /// A pixel is dark when it is below the local mean by more than this.
        var offset = 7
        /// Quad area / convex hull area of a candidate.
        var quadRatio = 0.85
    }

    static func detect(_ image: LumaImage, parameters: Parameters = Parameters()) -> [ArucoMarkerDetection] {
        guard image.width > 2, image.height > 2, image.pixels.count == image.width * image.height else { return [] }
        let integral = integralImage(image)

        var found: [Int: ArucoMarkerDetection] = [:]
        for radius in parameters.radii {
            for detection in detect(image, integral: integral, radius: radius, parameters: parameters)
            where found[detection.id] == nil {
                found[detection.id] = detection
            }
        }
        return found.values.sorted { $0.id < $1.id }
    }

    // MARK: - One threshold window

    private static func detect(
        _ image: LumaImage,
        integral: [UInt32],
        radius: Int,
        parameters: Parameters
    ) -> [ArucoMarkerDetection] {
        let w = image.width
        let h = image.height
        let stride = w + 1

        // 1. Adaptive threshold + 4-connected labeling (two-pass union-find).
        var labels = [Int32](repeating: 0, count: w * h)
        var parent: [Int32] = [0]

        func find(_ label: Int32) -> Int32 {
            var root = label
            while parent[Int(root)] != root { root = parent[Int(root)] }
            var node = label
            while parent[Int(node)] != root {
                let next = parent[Int(node)]
                parent[Int(node)] = root
                node = next
            }
            return root
        }

        image.pixels.withUnsafeBufferPointer { pixels in
            for y in 0..<h {
                let y0 = max(0, y - radius), y1 = min(h - 1, y + radius)
                for x in 0..<w {
                    let x0 = max(0, x - radius), x1 = min(w - 1, x + radius)
                    let sum = Int(integral[(y1 + 1) * stride + x1 + 1]) - Int(integral[y0 * stride + x1 + 1])
                        - Int(integral[(y1 + 1) * stride + x0]) + Int(integral[y0 * stride + x0])
                    let count = (x1 - x0 + 1) * (y1 - y0 + 1)
                    let index = y * w + x
                    guard (Int(pixels[index]) + parameters.offset) * count < sum else { continue }

                    let left: Int32 = x > 0 ? labels[index - 1] : 0
                    let up: Int32 = y > 0 ? labels[index - w] : 0
                    if left == 0 && up == 0 {
                        let label = Int32(parent.count)
                        parent.append(label)
                        labels[index] = label
                    } else if left != 0 && up != 0 {
                        let a = find(left), b = find(up)
                        labels[index] = min(a, b)
                        if a != b { parent[Int(max(a, b))] = min(a, b) }
                    } else {
                        labels[index] = max(left, up)
                    }
                }
            }
        }

        // 2. Resolve roots and gather bounding boxes and pixel counts.
        let labelCount = parent.count
        var minX = [Int32](repeating: Int32.max, count: labelCount)
        var maxX = [Int32](repeating: -1, count: labelCount)
        var minY = [Int32](repeating: Int32.max, count: labelCount)
        var maxY = [Int32](repeating: -1, count: labelCount)
        var area = [Int32](repeating: 0, count: labelCount)

        for y in 0..<h {
            for x in 0..<w {
                let index = y * w + x
                let label = labels[index]
                guard label != 0 else { continue }
                let root = find(label)
                labels[index] = root
                let r = Int(root)
                minX[r] = min(minX[r], Int32(x)); maxX[r] = max(maxX[r], Int32(x))
                minY[r] = min(minY[r], Int32(y)); maxY[r] = max(maxY[r], Int32(y))
                area[r] += 1
            }
        }

        // 3. Candidates: marker-sized dark blobs whose hull is a quadrilateral.
        var detections: [ArucoMarkerDetection] = []
        for r in 1..<labelCount where area[r] >= 80 && parent[r] == Int32(r) {
            let bw = Int(maxX[r] - minX[r]) + 1
            let bh = Int(maxY[r] - minY[r]) + 1
            guard max(bw, bh) >= 18, max(bw, bh) <= 400, min(bw, bh) >= 10 else { continue }

            var points: [SIMD2<Double>] = []
            for y in Int(minY[r])...Int(maxY[r]) {
                var first = -1, last = -1
                for x in Int(minX[r])...Int(maxX[r]) where labels[y * w + x] == Int32(r) {
                    if first < 0 { first = x }
                    last = x
                }
                guard first >= 0 else { continue }
                let x0 = Double(first) - 0.5, x1 = Double(last) + 0.5, yy = Double(y)
                points += [
                    SIMD2(x0, yy - 0.5), SIMD2(x1, yy - 0.5),
                    SIMD2(x0, yy + 0.5), SIMD2(x1, yy + 0.5)
                ]
            }

            let hull = convexHull(points)
            guard hull.count >= 4 else { continue }
            let quad = reduceToQuad(hull)
            let quadArea = polygonArea(quad)
            guard quadArea >= parameters.quadRatio * polygonArea(hull), quadArea >= 200 else { continue }

            let sides = (0..<4).map { simd_distance(quad[$0], quad[($0 + 1) % 4]) }
            guard let shortest = sides.min(), let longest = sides.max(),
                  shortest >= 12, longest / shortest <= 3 else { continue }

            let fill = Double(area[r]) / quadArea
            guard fill > 0.3, fill < 0.95 else { continue }

            if let detection = decode(quad: quad, image: image) {
                detections.append(detection)
            }
        }
        return detections
    }

    // MARK: - Decoding

    private static func decode(quad: [SIMD2<Double>], image: LumaImage) -> ArucoMarkerDetection? {
        let unit = [SIMD2<Double>(0, 0), SIMD2(6, 0), SIMD2(6, 6), SIMD2(0, 6)]

        for order in [quad, [quad[0], quad[3], quad[2], quad[1]]] {
            guard let H = homography(from: unit, to: order) else { return nil }

            var grid = [[Double]](repeating: [Double](repeating: 0, count: 6), count: 6)
            for row in 0..<6 {
                for column in 0..<6 {
                    var sum = 0.0
                    for dy in [-0.2, 0, 0.2] {
                        for dx in [-0.2, 0, 0.2] {
                            let p = apply(H, SIMD2(Double(column) + 0.5 + dx, Double(row) + 0.5 + dy))
                            guard let value = bilinear(image, p) else { return nil }
                            sum += value
                        }
                    }
                    grid[row][column] = sum / 9
                }
            }

            let values = grid.flatMap { $0 }
            guard let low = values.min(), let high = values.max(), high - low >= 30 else { return nil }
            let threshold = (low + high) / 2
            let bits = grid.map { $0.map { $0 > threshold ? UInt8(1) : UInt8(0) } }

            var borderWhite = 0
            for i in 0..<6 {
                borderWhite += Int(bits[0][i]) + Int(bits[5][i])
            }
            for i in 1..<5 {
                borderWhite += Int(bits[i][0]) + Int(bits[i][5])
            }
            guard borderWhite <= 1 else { return nil }

            for (id, pattern) in ArucoDictionary.cells.sorted(by: { $0.key < $1.key }) {
                var rotated = bits
                for k in 0..<4 {
                    if (1..<5).allSatisfy({ r in (1..<5).allSatisfy { c in rotated[r][c] == pattern[r][c] } }) {
                        let corners = (0..<4).map { order[(($0 - k) % 4 + 4) % 4] }
                        return ArucoMarkerDetection(id: id, corners: corners, center: apply(H, SIMD2(3, 3)))
                    }
                    rotated = rotateClockwise(rotated)
                }
            }
        }
        return nil
    }

    private static func rotateClockwise(_ grid: [[UInt8]]) -> [[UInt8]] {
        let n = grid.count
        return (0..<n).map { r in (0..<n).map { c in grid[n - 1 - c][r] } }
    }

    // MARK: - Geometry helpers

    private static func integralImage(_ image: LumaImage) -> [UInt32] {
        let w = image.width, h = image.height, stride = w + 1
        var integral = [UInt32](repeating: 0, count: stride * (h + 1))
        for y in 0..<h {
            var rowSum: UInt32 = 0
            for x in 0..<w {
                rowSum &+= UInt32(image.pixels[y * w + x])
                integral[(y + 1) * stride + x + 1] = integral[y * stride + x + 1] &+ rowSum
            }
        }
        return integral
    }

    static func convexHull(_ input: [SIMD2<Double>]) -> [SIMD2<Double>] {
        let points = Array(Set(input.map { [$0.x, $0.y] })).map { SIMD2($0[0], $0[1]) }
            .sorted { $0.x != $1.x ? $0.x < $1.x : $0.y < $1.y }
        guard points.count >= 3 else { return points }

        func cross(_ o: SIMD2<Double>, _ a: SIMD2<Double>, _ b: SIMD2<Double>) -> Double {
            (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
        }

        var lower: [SIMD2<Double>] = []
        for p in points {
            while lower.count >= 2 && cross(lower[lower.count - 2], lower[lower.count - 1], p) <= 0 { lower.removeLast() }
            lower.append(p)
        }
        var upper: [SIMD2<Double>] = []
        for p in points.reversed() {
            while upper.count >= 2 && cross(upper[upper.count - 2], upper[upper.count - 1], p) <= 0 { upper.removeLast() }
            upper.append(p)
        }
        return Array(lower.dropLast()) + Array(upper.dropLast())
    }

    static func polygonArea(_ polygon: [SIMD2<Double>]) -> Double {
        var sum = 0.0
        for i in polygon.indices {
            let a = polygon[i], b = polygon[(i + 1) % polygon.count]
            sum += a.x * b.y - b.x * a.y
        }
        return abs(sum) / 2
    }

    /// Removes the vertex spanning the smallest triangle until four remain.
    static func reduceToQuad(_ hull: [SIMD2<Double>]) -> [SIMD2<Double>] {
        var polygon = hull
        while polygon.count > 4 {
            var smallest = 0
            var smallestArea = Double.greatestFiniteMagnitude
            for i in polygon.indices {
                let triangle = [
                    polygon[(i - 1 + polygon.count) % polygon.count],
                    polygon[i],
                    polygon[(i + 1) % polygon.count]
                ]
                let a = polygonArea(triangle)
                if a < smallestArea {
                    smallestArea = a
                    smallest = i
                }
            }
            polygon.remove(at: smallest)
        }
        return polygon
    }

    /// 3 × 3 homography (row-major, h33 = 1) mapping `source` onto `target` (4 points each).
    static func homography(from source: [SIMD2<Double>], to target: [SIMD2<Double>]) -> [Double]? {
        var a = [[Double]](repeating: [Double](repeating: 0, count: 9), count: 8)
        for i in 0..<4 {
            let (x, y) = (source[i].x, source[i].y)
            let (u, v) = (target[i].x, target[i].y)
            a[2 * i] = [x, y, 1, 0, 0, 0, -u * x, -u * y, u]
            a[2 * i + 1] = [0, 0, 0, x, y, 1, -v * x, -v * y, v]
        }
        // Gaussian elimination with partial pivoting on the augmented 8 × 9 system.
        for column in 0..<8 {
            guard let pivot = (column..<8).max(by: { abs(a[$0][column]) < abs(a[$1][column]) }),
                  abs(a[pivot][column]) > 1e-12 else { return nil }
            a.swapAt(column, pivot)
            for row in 0..<8 where row != column {
                let factor = a[row][column] / a[column][column]
                if factor != 0 {
                    for k in column..<9 { a[row][k] -= factor * a[column][k] }
                }
            }
        }
        return (0..<8).map { a[$0][8] / a[$0][$0] } + [1]
    }

    static func apply(_ H: [Double], _ p: SIMD2<Double>) -> SIMD2<Double> {
        let x = H[0] * p.x + H[1] * p.y + H[2]
        let y = H[3] * p.x + H[4] * p.y + H[5]
        let z = H[6] * p.x + H[7] * p.y + H[8]
        return SIMD2(x / z, y / z)
    }

    private static func bilinear(_ image: LumaImage, _ p: SIMD2<Double>) -> Double? {
        let x0 = Int(floor(p.x)), y0 = Int(floor(p.y))
        guard x0 >= 0, y0 >= 0, x0 + 1 < image.width, y0 + 1 < image.height else { return nil }
        let fx = p.x - Double(x0), fy = p.y - Double(y0)
        let w = image.width
        let v00 = Double(image.pixels[y0 * w + x0]), v10 = Double(image.pixels[y0 * w + x0 + 1])
        let v01 = Double(image.pixels[(y0 + 1) * w + x0]), v11 = Double(image.pixels[(y0 + 1) * w + x0 + 1])
        return v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) + v01 * (1 - fx) * fy + v11 * fx * fy
    }
}
