import CoreGraphics
import CoreVideo
import Foundation

struct CapsuleDetection {
    enum Kind: Equatable {
        case white
        case orange
    }

    let kind: Kind
    let centroidPixel: CGPoint
    let contourPixel: CGPoint
    let selectedPixel: CGPoint
    let centerDeltaPixels: CGFloat
    let diameterPixels: CGFloat
}

enum CapsuleDetector {
    static func detect(
        pixelBuffer: CVPixelBuffer,
        mode: CapsuleCenterMode,
        whiteThreshold: Double
    ) -> [CapsuleDetection] {
        guard CVPixelBufferGetPlaneCount(pixelBuffer) >= 2 else { return [] }

        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }

        guard
            let yBaseRaw = CVPixelBufferGetBaseAddressOfPlane(pixelBuffer, 0),
            let cbcrBaseRaw = CVPixelBufferGetBaseAddressOfPlane(pixelBuffer, 1)
        else { return [] }

        let width = CVPixelBufferGetWidthOfPlane(pixelBuffer, 0)
        let height = CVPixelBufferGetHeightOfPlane(pixelBuffer, 0)
        let yStride = CVPixelBufferGetBytesPerRowOfPlane(pixelBuffer, 0)
        let cbcrStride = CVPixelBufferGetBytesPerRowOfPlane(pixelBuffer, 1)

        let yBase = yBaseRaw.assumingMemoryBound(to: UInt8.self)
        let cbcrBase = cbcrBaseRaw.assumingMemoryBound(to: UInt8.self)

        let step = 4
        let gridW = max(1, width / step)
        let gridH = max(1, height / step)

        // 0 = none, 1 = white capsule candidate, 2 = orange test marker.
        var mask = [UInt8](repeating: 0, count: gridW * gridH)
        let yThreshold = UInt8(clamping: Int(whiteThreshold * 255.0))

        for gy in 0..<gridH {
            let py = min(height - 1, gy * step + step / 2)
            for gx in 0..<gridW {
                let px = min(width - 1, gx * step + step / 2)

                let yy = Int(yBase[py * yStride + px])
                let chromaIndex = (py / 2) * cbcrStride + (px / 2) * 2
                let cb = Int(cbcrBase[chromaIndex])
                let cr = Int(cbcrBase[chromaIndex + 1])

                let idx = gy * gridW + gx

                // Orange/red test dot: high Cr, lower Cb.
                if yy > 65 && cr > 150 && cb < 125 {
                    mask[idx] = 2
                    continue
                }

                // White / neutral capsule: high luma and weak chroma.
                if yy >= Int(yThreshold) && abs(cb - 128) < 24 && abs(cr - 128) < 24 {
                    mask[idx] = 1
                }
            }
        }

        var visited = [Bool](repeating: false, count: mask.count)
        var detections: [CapsuleDetection] = []
        detections.reserveCapacity(128)

        for gy in 0..<gridH {
            for gx in 0..<gridW {
                let start = gy * gridW + gx
                let label = mask[start]
                if label == 0 || visited[start] { continue }

                var stack = [start]
                visited[start] = true

                var component: [(Int, Int)] = []
                var minX = gx, maxX = gx, minY = gy, maxY = gy
                var sumX = 0.0, sumY = 0.0

                while let q = stack.popLast() {
                    let qy = q / gridW
                    let qx = q - qy * gridW

                    component.append((qx, qy))
                    minX = min(minX, qx)
                    maxX = max(maxX, qx)
                    minY = min(minY, qy)
                    maxY = max(maxY, qy)
                    sumX += Double(qx)
                    sumY += Double(qy)

                    let neighbors = [
                        (qx - 1, qy), (qx + 1, qy),
                        (qx, qy - 1), (qx, qy + 1)
                    ]

                    for (nx, ny) in neighbors {
                        guard nx >= 0, nx < gridW, ny >= 0, ny < gridH else { continue }
                        let ni = ny * gridW + nx
                        if !visited[ni] && mask[ni] == label {
                            visited[ni] = true
                            stack.append(ni)
                        }
                    }
                }

                let n = component.count
                if n < 2 { continue }

                let bboxW = maxX - minX + 1
                let bboxH = maxY - minY + 1
                let diameterPx = CGFloat(max(bboxW, bboxH) * step)
                let aspect = Double(bboxW) / Double(max(1, bboxH))
                let fill = Double(n) / Double(max(1, bboxW * bboxH))

                if label == 1 {
                    guard diameterPx >= 6, diameterPx <= 100 else { continue }
                    guard aspect > 0.42, aspect < 2.35 else { continue }
                    guard fill > 0.18, fill < 0.98 else { continue }
                } else {
                    guard diameterPx >= 3, diameterPx <= 80 else { continue }
                }

                let meanGX = sumX / Double(n)
                let meanGY = sumY / Double(n)
                let centroid = CGPoint(
                    x: (meanGX + 0.5) * Double(step),
                    y: (meanGY + 0.5) * Double(step)
                )

                // Boundary points for a simple ellipse/contour center estimate.
                var boundary: [(Double, Double)] = []
                boundary.reserveCapacity(component.count)

                for (qx, qy) in component {
                    let neighbors = [
                        (qx - 1, qy), (qx + 1, qy),
                        (qx, qy - 1), (qx, qy + 1)
                    ]
                    let isBoundary = neighbors.contains { nx, ny in
                        guard nx >= 0, nx < gridW, ny >= 0, ny < gridH else { return true }
                        return mask[ny * gridW + nx] != label
                    }
                    if isBoundary {
                        boundary.append((Double(qx), Double(qy)))
                    }
                }

                let contour = contourCenter(
                    boundary: boundary,
                    fallbackX: meanGX,
                    fallbackY: meanGY,
                    step: step
                )

                let selected: CGPoint
                switch mode {
                case .centroid:
                    selected = centroid
                case .contour, .compare:
                    selected = contour
                }

                detections.append(
                    CapsuleDetection(
                        kind: label == 2 ? .orange : .white,
                        centroidPixel: centroid,
                        contourPixel: contour,
                        selectedPixel: selected,
                        centerDeltaPixels: hypot(
                            contour.x - centroid.x,
                            contour.y - centroid.y
                        ),
                        diameterPixels: diameterPx
                    )
                )
            }
        }

        // Keep the strongest-looking components spatially separated.
        detections.sort { $0.diameterPixels > $1.diameterPixels }
        var filtered: [CapsuleDetection] = []

        for detection in detections {
            let minDistance = max(7.0, detection.diameterPixels * 0.55)
            let duplicate = filtered.contains {
                hypot(
                    $0.selectedPixel.x - detection.selectedPixel.x,
                    $0.selectedPixel.y - detection.selectedPixel.y
                ) < minDistance
            }
            if !duplicate {
                filtered.append(detection)
            }
        }

        return filtered
    }

    private static func contourCenter(
        boundary: [(Double, Double)],
        fallbackX: Double,
        fallbackY: Double,
        step: Int
    ) -> CGPoint {
        guard boundary.count >= 6 else {
            return CGPoint(
                x: (fallbackX + 0.5) * Double(step),
                y: (fallbackY + 0.5) * Double(step)
            )
        }

        let count = Double(boundary.count)
        let mx = boundary.reduce(0.0) { $0 + $1.0 } / count
        let my = boundary.reduce(0.0) { $0 + $1.1 } / count

        var cxx = 0.0
        var cxy = 0.0
        var cyy = 0.0

        for (x, y) in boundary {
            let dx = x - mx
            let dy = y - my
            cxx += dx * dx
            cxy += dx * dy
            cyy += dy * dy
        }

        let theta = 0.5 * atan2(2.0 * cxy, cxx - cyy)
        let ux = cos(theta)
        let uy = sin(theta)
        let vx = -uy
        let vy = ux

        var uMin = Double.greatestFiniteMagnitude
        var uMax = -Double.greatestFiniteMagnitude
        var vMin = Double.greatestFiniteMagnitude
        var vMax = -Double.greatestFiniteMagnitude

        for (x, y) in boundary {
            let dx = x - mx
            let dy = y - my
            let u = dx * ux + dy * uy
            let v = dx * vx + dy * vy
            uMin = min(uMin, u)
            uMax = max(uMax, u)
            vMin = min(vMin, v)
            vMax = max(vMax, v)
        }

        let uMid = 0.5 * (uMin + uMax)
        let vMid = 0.5 * (vMin + vMax)
        let cx = mx + uMid * ux + vMid * vx
        let cy = my + uMid * uy + vMid * vy

        return CGPoint(
            x: (cx + 0.5) * Double(step),
            y: (cy + 0.5) * Double(step)
        )
    }
}
