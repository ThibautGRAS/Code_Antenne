import ARKit
import CoreImage
import Foundation
import ImageIO
import simd

/// Diagnostic recording of a real scan, for offline replay of the whole pipeline on a PC:
/// one camera image every `interval` seconds (JPEG, full resolution, sensor orientation) plus
/// one JSON line per image with the ARKit camera pose, intrinsics, tracking state, the ArUco
/// image anchors in view and the locked face. Packed into a single zip when stopped.
///
/// Folder layout: meta.json, frames.jsonl, images/000001.jpg …
final class ScanRecorder {
    private let queue = DispatchQueue(label: "CubeMEMS.ScanRecorder", qos: .utility)
    private let context = CIContext()
    private var directory: URL?
    private var framesHandle: FileHandle?
    private var lastTimestamp: TimeInterval = -.greatestFiniteMagnitude
    private(set) var frameCount = 0

    var interval: TimeInterval = 0.5
    var isRecording: Bool { directory != nil }

    func start(meta: [String: Any]) throws {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let folder = FileManager.default.temporaryDirectory
            .appendingPathComponent("CubeMEMS_enregistrement_\(formatter.string(from: Date()))")

        try FileManager.default.createDirectory(
            at: folder.appendingPathComponent("images"),
            withIntermediateDirectories: true
        )
        let metaData = try JSONSerialization.data(withJSONObject: meta, options: [.prettyPrinted, .sortedKeys])
        try metaData.write(to: folder.appendingPathComponent("meta.json"))

        let framesURL = folder.appendingPathComponent("frames.jsonl")
        FileManager.default.createFile(atPath: framesURL.path, contents: nil)
        framesHandle = try FileHandle(forWritingTo: framesURL)

        directory = folder
        frameCount = 0
        lastTimestamp = -.greatestFiniteMagnitude
    }

    /// Call for every ARFrame; keeps one every `interval` seconds. Returns true when kept.
    @discardableResult
    func record(
        frame: ARFrame,
        face: simd_float4x4?,
        faceSize: SIMD2<Float>,
        planeOffset: Float,
        markers: [Int: simd_float4x4]
    ) -> Bool {
        guard let directory, let framesHandle, frame.timestamp - lastTimestamp >= interval else { return false }
        lastTimestamp = frame.timestamp
        frameCount += 1

        let index = frameCount
        let imageName = String(format: "images/%06d.jpg", index)
        let pixelBuffer = frame.capturedImage

        var line: [String: Any] = [
            "index": index,
            "timestamp": frame.timestamp,
            "image": imageName,
            "imageWidth": CVPixelBufferGetWidth(pixelBuffer),
            "imageHeight": CVPixelBufferGetHeight(pixelBuffer),
            "camera": Self.array(frame.camera.transform),
            "intrinsics": Self.array(frame.camera.intrinsics),
            "tracking": Self.describe(frame.camera.trackingState),
            "markers": Dictionary(uniqueKeysWithValues: markers.map { ("\($0.key)", Self.array($0.value)) }),
            "planeOffset": planeOffset
        ]
        if let face {
            line["face"] = Self.array(face)
            line["faceSize"] = [faceSize.x, faceSize.y]
        }

        // JPEG encoding off the ARKit delegate thread; the pixel buffer is retained only until then.
        queue.async { [context] in
            let image = CIImage(cvPixelBuffer: pixelBuffer)
            if let jpeg = context.jpegRepresentation(
                of: image,
                colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!,
                options: [CIImageRepresentationOption(rawValue: kCGImageDestinationLossyCompressionQuality as String): 0.8]
            ) {
                try? jpeg.write(to: directory.appendingPathComponent(imageName))
            }
            if let data = try? JSONSerialization.data(withJSONObject: line, options: [.sortedKeys]) {
                framesHandle.write(data)
                framesHandle.write(Data("\n".utf8))
            }
        }
        return true
    }

    /// Finishes pending writes, zips the folder and returns the zip URL.
    func stop(completion: @escaping (Result<URL, Error>) -> Void) {
        guard let directory, let framesHandle else { return }
        self.directory = nil
        self.framesHandle = nil

        queue.async {
            try? framesHandle.close()

            var coordinatorError: NSError?
            var result: Result<URL, Error> = .failure(CocoaError(.fileWriteUnknown))
            // .forUploading hands back a temporary zip of the folder.
            NSFileCoordinator().coordinate(readingItemAt: directory, options: .forUploading, error: &coordinatorError) { zipURL in
                let destination = directory.deletingLastPathComponent()
                    .appendingPathComponent(directory.lastPathComponent + ".zip")
                do {
                    try? FileManager.default.removeItem(at: destination)
                    try FileManager.default.copyItem(at: zipURL, to: destination)
                    result = .success(destination)
                } catch {
                    result = .failure(error)
                }
            }
            if let coordinatorError {
                result = .failure(coordinatorError)
            }
            try? FileManager.default.removeItem(at: directory)
            DispatchQueue.main.async { completion(result) }
        }
    }

    // MARK: - JSON helpers (column-major, like simd)

    private static func array(_ m: simd_float4x4) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2, m.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] }
    }

    private static func array(_ m: simd_float3x3) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2].flatMap { [$0.x, $0.y, $0.z] }
    }

    private static func describe(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal: return "normal"
        case .notAvailable: return "notAvailable"
        case .limited(let reason):
            switch reason {
            case .initializing: return "limited:initializing"
            case .excessiveMotion: return "limited:excessiveMotion"
            case .insufficientFeatures: return "limited:insufficientFeatures"
            case .relocalizing: return "limited:relocalizing"
            @unknown default: return "limited:unknown"
            }
        @unknown default: return "unknown"
        }
    }
}
