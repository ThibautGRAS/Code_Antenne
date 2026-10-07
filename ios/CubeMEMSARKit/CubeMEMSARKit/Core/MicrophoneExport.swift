import Foundation
import simd

// Numbering and CSV export of the confirmed microphones, in the face frame:
// origin = center of the four ArUco, X to the right and Y up as seen when facing the grid,
// Z = face normal toward the operator. Units: meters.

struct NumberedMicrophone {
    /// 1-based channel order (row of the geometry file).
    var number: Int
    /// 1 = rightmost column (seen facing the grid).
    var column: Int
    /// 1 = lowest microphone of its column.
    var row: Int
    var position: SIMD3<Float>
    var uncertainty: Float
    var rays: Int
    var residual: Float
}

enum MicrophoneNumbering {
    /// Splits the microphones into columns (a new column starts where the X gap between
    /// neighbours exceeds `columnGap`), then numbers them: rightmost column first, bottom to
    /// top, then the next column to the left, bottom to top, and so on.
    static func number(_ tracks: [MicroTrack], columnGap: Float) -> [NumberedMicrophone] {
        let points = tracks
            .filter { $0.state == .confirmed }
            .compactMap { track -> (track: MicroTrack, local: SIMD3<Float>)? in
                guard let local = track.localPoint else { return nil }
                return (track, local)
            }
            .sorted { $0.local.x > $1.local.x }

        var columns: [[(track: MicroTrack, local: SIMD3<Float>)]] = []
        for point in points {
            if let previous = columns.last?.last, previous.local.x - point.local.x <= columnGap {
                columns[columns.count - 1].append(point)
            } else {
                columns.append([point])
            }
        }

        var result: [NumberedMicrophone] = []
        for (columnIndex, column) in columns.enumerated() {
            for (rowIndex, point) in column.sorted(by: { $0.local.y < $1.local.y }).enumerated() {
                result.append(
                    NumberedMicrophone(
                        number: result.count + 1,
                        column: columnIndex + 1,
                        row: rowIndex + 1,
                        position: point.local,
                        uncertainty: point.track.uncertainty,
                        rays: point.track.rays.count,
                        residual: point.track.residual
                    )
                )
            }
        }
        return result
    }
}

enum MicrophoneExport {
    /// Same format as data/data_geo/*.csv of the beamforming tools: "X;Y;Z" in meters,
    /// one row per microphone in channel order.
    static func geometryCSV(_ microphones: [NumberedMicrophone]) -> String {
        var lines = ["X;Y;Z"]
        for microphone in microphones {
            lines.append(
                String(
                    format: "%.5f;%.5f;%.5f",
                    microphone.position.x, microphone.position.y, microphone.position.z
                )
            )
        }
        return lines.joined(separator: "\n") + "\n"
    }

    /// Everything known about each microphone, for checking the scan.
    static func detailedCSV(_ microphones: [NumberedMicrophone]) -> String {
        var lines = ["num;colonne;rang;X_m;Y_m;Z_m;incertitude_mm;rayons;residu_mm"]
        for microphone in microphones {
            lines.append(
                String(
                    format: "%d;%d;%d;%.5f;%.5f;%.5f;%.1f;%d;%.1f",
                    microphone.number, microphone.column, microphone.row,
                    microphone.position.x, microphone.position.y, microphone.position.z,
                    microphone.uncertainty * 1000, microphone.rays, microphone.residual * 1000
                )
            )
        }
        return lines.joined(separator: "\n") + "\n"
    }
}
