import ARKit
import RealityKit
import SwiftUI
import UIKit
import simd

struct ARScannerView: UIViewRepresentable {
    @ObservedObject var model: ScanModel

    func makeCoordinator() -> Coordinator {
        Coordinator(model: model)
    }

    func makeUIView(context: Context) -> ARView {
        let view = ARView(
            frame: .zero,
            cameraMode: .ar,
            automaticallyConfigureSession: false
        )
        context.coordinator.attach(view)
        context.coordinator.startSession(resetTracking: true)
        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        context.coordinator.syncFromModel()
    }

    final class Coordinator: NSObject, ARSessionDelegate {
        private weak var arView: ARView?
        private let model: ScanModel
        private let detectorQueue = DispatchQueue(label: "CubeMEMS.CapsuleDetector", qos: .userInitiated)

        private var markerCenters: [Int: SIMD3<Float>] = [:]
        private var markerVisuals: [Int: AnchorEntity] = [:]

        private var faceTransform: simd_float4x4?
        private var faceWidth: Float = 2.0
        private var faceHeight: Float = 2.0
        private var faceAnchor: AnchorEntity?
        private var microAnchor: AnchorEntity?

        private var tracks: [MicroTrack] = []
        private var frameCounter = 0
        private var lastDetectionTime: TimeInterval = 0
        private var detectionRunning = false
        private var lastCameraTransform: simd_float4x4?
        private var lastCameraTimestamp: TimeInterval?

        private var lastResetToken: UUID
        private var lastMarkerSizeCm: Double

        init(model: ScanModel) {
            self.model = model
            self.lastResetToken = model.resetToken
            self.lastMarkerSizeCm = model.markerSizeCm
            super.init()
        }

        func attach(_ view: ARView) {
            arView = view
            view.session.delegate = self

            let root = AnchorEntity(world: SIMD3<Float>(repeating: 0))
            view.scene.addAnchor(root)
            microAnchor = root
        }

        func startSession(resetTracking: Bool) {
            guard let arView else { return }

            let configuration = ARWorldTrackingConfiguration()
            configuration.worldAlignment = .gravity
            configuration.environmentTexturing = .automatic
            configuration.maximumNumberOfTrackedImages = 4
            configuration.detectionImages = ArucoReferenceFactory.makeReferenceImages(
                markerWidthMeters: CGFloat(model.markerSizeCm / 100.0)
            )

            let options: ARSession.RunOptions = resetTracking
                ? [.resetTracking, .removeExistingAnchors]
                : []

            arView.session.run(configuration, options: options)
        }

        func syncFromModel() {
            if lastResetToken != model.resetToken {
                lastResetToken = model.resetToken
                resetAll()
                return
            }

            if abs(lastMarkerSizeCm - model.markerSizeCm) > 0.001 {
                lastMarkerSizeCm = model.markerSizeCm
                resetAll()
            }
        }

        private func resetAll() {
            markerCenters.removeAll()
            tracks.removeAll()
            frameCounter = 0
            lastCameraTransform = nil
            lastCameraTimestamp = nil
            faceTransform = nil
            faceWidth = 2
            faceHeight = 2

            for anchor in markerVisuals.values {
                arView?.scene.removeAnchor(anchor)
            }
            markerVisuals.removeAll()

            if let faceAnchor {
                arView?.scene.removeAnchor(faceAnchor)
            }
            faceAnchor = nil

            microAnchor?.children.removeAll()
            startSession(resetTracking: true)

            Task { @MainActor in
                model.visibleMarkerIDs = []
                model.mappedMarkerIDs = []
                model.faceLocked = false
                model.confirmedMicros = 0
                model.provisionalMicros = 0
                model.rejectedMicros = 0
                model.meanCenterDeltaMm = nil
                model.status = "Repère AR réinitialisé. Montre les ArUco un par un."
            }
        }

        // MARK: - AR session

        func session(_ session: ARSession, didAdd anchors: [ARAnchor]) {
            updateImageAnchors(anchors)
        }

        func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
            updateImageAnchors(anchors)
        }

        func session(_ session: ARSession, didUpdate frame: ARFrame) {
            frameCounter += 1

            let visible = Set(
                frame.anchors.compactMap { anchor -> Int? in
                    guard let image = anchor as? ARImageAnchor, image.isTracked else { return nil }
                    return markerID(from: image.referenceImage.name)
                }
            )

            let tooFast = cameraMotionTooFast(frame)
            let trackingUsable: Bool
            switch frame.camera.trackingState {
            case .normal:
                trackingUsable = true
            default:
                trackingUsable = false
            }

            Task { @MainActor in
                model.visibleMarkerIDs = visible

                switch frame.camera.trackingState {
                case .normal:
                    if model.isScanning {
                        if faceTransform == nil {
                            model.status = "Tracking AR OK. Parcours les quatre ArUco ; ils sont mémorisés."
                        } else if tooFast {
                            model.status = "Mouvement rapide : rectangle conservé, détection micros temporairement suspendue."
                        } else {
                            model.status = "Face verrouillée. Déplace-toi doucement et latéralement pour trianguler les capsules."
                        }
                    }
                case .limited(let reason):
                    model.status = "Tracking AR limité : \(reason.description)"
                case .notAvailable:
                    model.status = "Tracking AR indisponible."
                @unknown default:
                    break
                }
            }

            guard model.isScanning, faceTransform != nil, trackingUsable, !tooFast else { return }

            let now = frame.timestamp
            guard now - lastDetectionTime > 0.20, !detectionRunning else { return }
            lastDetectionTime = now
            detectionRunning = true

            let pixelBuffer = frame.capturedImage
            let centerMode = model.centerMode
            let threshold = model.whiteThreshold

            detectorQueue.async { [weak self] in
                guard let self else { return }

                let detections = CapsuleDetector.detect(
                    pixelBuffer: pixelBuffer,
                    mode: centerMode,
                    whiteThreshold: threshold
                )

                DispatchQueue.main.async { [weak self] in
                    guard let self else { return }
                    self.consume(detections: detections, frame: frame)
                    self.detectionRunning = false
                }
            }
        }

        private func cameraMotionTooFast(_ frame: ARFrame) -> Bool {
            defer {
                lastCameraTransform = frame.camera.transform
                lastCameraTimestamp = frame.timestamp
            }

            guard
                let previous = lastCameraTransform,
                let previousTime = lastCameraTimestamp
            else { return false }

            let dt = max(1e-3, frame.timestamp - previousTime)
            let current = frame.camera.transform

            let p0 = previous.translation
            let p1 = current.translation
            let translationSpeed = simd_distance(p0, p1) / Float(dt)

            let f0 = simd_normalize(SIMD3<Float>(
                previous.columns.2.x,
                previous.columns.2.y,
                previous.columns.2.z
            ))
            let f1 = simd_normalize(SIMD3<Float>(
                current.columns.2.x,
                current.columns.2.y,
                current.columns.2.z
            ))
            let cosine = max(-1.0 as Float, min(1.0 as Float, simd_dot(f0, f1)))
            let angularSpeed = acos(cosine) / Float(dt)

            // Tuned from the first iPhone walk-around video:
            // keep ARKit tracking alive, but do not add blurred capsule rays
            // during fast pans.
            return translationSpeed > 1.2 || angularSpeed > 1.6
        }

        func session(_ session: ARSession, didFailWithError error: Error) {
            Task { @MainActor in
                model.status = "Erreur ARKit : \(error.localizedDescription)"
            }
        }

        // MARK: - Marker mapping

        private func updateImageAnchors(_ anchors: [ARAnchor]) {
            guard model.isScanning else { return }

            for anchor in anchors {
                guard
                    let image = anchor as? ARImageAnchor,
                    image.isTracked,
                    let id = markerID(from: image.referenceImage.name)
                else { continue }

                let p = image.transform.translation

                if let old = markerCenters[id] {
                    // Low-pass only while the face is not locked. Once locked,
                    // the geometry is frozen to avoid visible jumps.
                    if faceTransform == nil {
                        markerCenters[id] = old * 0.75 + p * 0.25
                    }
                } else {
                    markerCenters[id] = p
                }

                updateMarkerVisual(id: id, position: markerCenters[id] ?? p)
            }

            Task { @MainActor in
                model.mappedMarkerIDs = Set(markerCenters.keys)
            }

            lockFaceIfReady()
        }

        private func markerID(from name: String?) -> Int? {
            guard let name, name.hasPrefix("aruco_") else { return nil }
            return Int(name.replacingOccurrences(of: "aruco_", with: ""))
        }

        private func updateMarkerVisual(id: Int, position: SIMD3<Float>) {
            guard let arView else { return }

            if let old = markerVisuals[id] {
                old.position = position
                return
            }

            let anchor = AnchorEntity(world: position)
            let mesh = MeshResource.generateSphere(radius: 0.025)
            var material = SimpleMaterial()
            material.color = .init(tint: .systemBlue, texture: nil)
            let sphere = ModelEntity(mesh: mesh, materials: [material])
            anchor.addChild(sphere)
            arView.scene.addAnchor(anchor)
            markerVisuals[id] = anchor
        }

        private func lockFaceIfReady() {
            guard faceTransform == nil else { return }
            guard
                let p0 = markerCenters[0],
                let p1 = markerCenters[1],
                let p2 = markerCenters[2],
                let p3 = markerCenters[3]
            else { return }

            let left = 0.5 * (p0 + p3)
            let right = 0.5 * (p1 + p2)
            let top = 0.5 * (p0 + p1)
            let bottom = 0.5 * (p3 + p2)

            var xAxis = simd_normalize(right - left)
            var yAxis = simd_normalize(top - bottom)
            var normal = simd_normalize(simd_cross(xAxis, yAxis))
            yAxis = simd_normalize(simd_cross(normal, xAxis))
            xAxis = simd_normalize(simd_cross(yAxis, normal))
            normal = simd_normalize(simd_cross(xAxis, yAxis))

            let center = 0.25 * (p0 + p1 + p2 + p3)

            faceWidth = 0.5 * (
                simd_distance(p0, p1) +
                simd_distance(p3, p2)
            )
            faceHeight = 0.5 * (
                simd_distance(p0, p3) +
                simd_distance(p1, p2)
            )

            // Reject an absurd acquisition, but allow a generous range for the prototype.
            guard faceWidth > 1.0, faceWidth < 3.2, faceHeight > 1.0, faceHeight < 3.2 else {
                Task { @MainActor in
                    model.status = String(
                        format: "Géométrie ArUco incohérente : %.2f × %.2f m. Réinitialise et rescane.",
                        faceWidth, faceHeight
                    )
                }
                return
            }

            var transform = matrix_identity_float4x4
            transform.columns.0 = SIMD4<Float>(xAxis.x, xAxis.y, xAxis.z, 0)
            transform.columns.1 = SIMD4<Float>(yAxis.x, yAxis.y, yAxis.z, 0)
            transform.columns.2 = SIMD4<Float>(normal.x, normal.y, normal.z, 0)
            transform.columns.3 = SIMD4<Float>(center.x, center.y, center.z, 1)

            faceTransform = transform
            renderLockedFace()

            Task { @MainActor in
                model.faceLocked = true
                model.status = String(
                    format: "Face verrouillée : %.2f × %.2f m. Les ArUco peuvent sortir du champ.",
                    faceWidth, faceHeight
                )
            }
        }

        private func renderLockedFace() {
            guard let arView, let faceTransform else { return }

            if let old = faceAnchor {
                arView.scene.removeAnchor(old)
            }

            let anchor = AnchorEntity(world: faceTransform)
            faceAnchor = anchor

            let lineThickness: Float = 0.008
            var borderMaterial = SimpleMaterial()
            borderMaterial.color = .init(tint: .systemGreen, texture: nil)

            let hMesh = MeshResource.generateBox(
                size: SIMD3<Float>(faceWidth, lineThickness, lineThickness)
            )
            let vMesh = MeshResource.generateBox(
                size: SIMD3<Float>(lineThickness, faceHeight, lineThickness)
            )

            let top = ModelEntity(mesh: hMesh, materials: [borderMaterial])
            top.position = [0, faceHeight / 2, 0]
            anchor.addChild(top)

            let bottom = ModelEntity(mesh: hMesh, materials: [borderMaterial])
            bottom.position = [0, -faceHeight / 2, 0]
            anchor.addChild(bottom)

            let left = ModelEntity(mesh: vMesh, materials: [borderMaterial])
            left.position = [-faceWidth / 2, 0, 0]
            anchor.addChild(left)

            let right = ModelEntity(mesh: vMesh, materials: [borderMaterial])
            right.position = [faceWidth / 2, 0, 0]
            anchor.addChild(right)

            // A very thin translucent box shows the nominal microphone plane.
            let offset = Float(model.planeOffsetCm / 100.0)
            let planeMesh = MeshResource.generateBox(
                size: SIMD3<Float>(faceWidth, faceHeight, 0.002)
            )
            var planeMaterial = SimpleMaterial()
            planeMaterial.color = .init(
                tint: UIColor.systemTeal.withAlphaComponent(0.10),
                texture: nil
            )

            let plane = ModelEntity(mesh: planeMesh, materials: [planeMaterial])
            plane.position = [0, 0, offset]
            anchor.addChild(plane)

            arView.scene.addAnchor(anchor)
        }

        // MARK: - Capsule reconstruction

        private func consume(detections: [CapsuleDetection], frame: ARFrame) {
            guard
                let arView,
                let faceTransform
            else { return }

            let orientation = arView.window?.windowScene?.interfaceOrientation ?? .portrait
            let viewport = arView.bounds.size
            let imageWidth = CGFloat(CVPixelBufferGetWidth(frame.capturedImage))
            let imageHeight = CGFloat(CVPixelBufferGetHeight(frame.capturedImage))

            let displayTransform = frame.displayTransform(
                for: orientation,
                viewportSize: viewport
            )

            var observations: [DetectionObservation] = []
            var centerDeltasMm: [Double] = []

            for detection in detections {
                let selectedScreen = screenPoint(
                    imagePixel: detection.selectedPixel,
                    imageWidth: imageWidth,
                    imageHeight: imageHeight,
                    displayTransform: displayTransform,
                    viewport: viewport
                )

                guard let ray = arView.ray(through: selectedScreen) else { continue }
                guard let nominal = nominalIntersection(
                    origin: ray.origin,
                    direction: ray.direction
                ) else { continue }

                if model.centerMode == .compare, detection.kind == .white {
                    let cScreen = screenPoint(
                        imagePixel: detection.centroidPixel,
                        imageWidth: imageWidth,
                        imageHeight: imageHeight,
                        displayTransform: displayTransform,
                        viewport: viewport
                    )
                    let eScreen = screenPoint(
                        imagePixel: detection.contourPixel,
                        imageWidth: imageWidth,
                        imageHeight: imageHeight,
                        displayTransform: displayTransform,
                        viewport: viewport
                    )

                    if
                        let cRay = arView.ray(through: cScreen),
                        let eRay = arView.ray(through: eScreen),
                        let cPoint = nominalIntersection(origin: cRay.origin, direction: cRay.direction),
                        let ePoint = nominalIntersection(origin: eRay.origin, direction: eRay.direction)
                    {
                        let delta = simd_distance(cPoint.world, ePoint.world)
                        centerDeltasMm.append(Double(delta * 1000))
                    }
                }

                observations.append(
                    DetectionObservation(
                        kind: detection.kind,
                        ray: RayObservation(
                            origin: ray.origin,
                            direction: simd_normalize(ray.direction)
                        ),
                        localXY: SIMD2<Float>(nominal.local.x, nominal.local.y)
                    )
                )
            }

            updateTracks(with: observations)

            Task { @MainActor in
                if !centerDeltasMm.isEmpty {
                    model.meanCenterDeltaMm =
                        centerDeltasMm.reduce(0, +) / Double(centerDeltasMm.count)
                }
            }
        }

        private func screenPoint(
            imagePixel: CGPoint,
            imageWidth: CGFloat,
            imageHeight: CGFloat,
            displayTransform: CGAffineTransform,
            viewport: CGSize
        ) -> CGPoint {
            let normalized = CGPoint(
                x: imagePixel.x / imageWidth,
                y: imagePixel.y / imageHeight
            )
            let viewNormalized = normalized.applying(displayTransform)
            return CGPoint(
                x: viewNormalized.x * viewport.width,
                y: viewNormalized.y * viewport.height
            )
        }

        private func nominalIntersection(
            origin: SIMD3<Float>,
            direction: SIMD3<Float>
        ) -> (world: SIMD3<Float>, local: SIMD3<Float>)? {
            guard let faceTransform else { return nil }

            let offset = Float(model.planeOffsetCm / 100.0)
            let localPlanePoint = SIMD4<Float>(0, 0, offset, 1)
            let worldPlanePoint4 = faceTransform * localPlanePoint
            let worldPlanePoint = SIMD3<Float>(
                worldPlanePoint4.x,
                worldPlanePoint4.y,
                worldPlanePoint4.z
            )

            let normal = simd_normalize(faceTransform.zAxis)
            let denom = simd_dot(direction, normal)
            guard abs(denom) > 1e-5 else { return nil }

            let distance = simd_dot(worldPlanePoint - origin, normal) / denom
            guard distance > 0 else { return nil }

            let worldPoint = origin + direction * distance
            let local4 = simd_inverse(faceTransform) * SIMD4<Float>(
                worldPoint.x,
                worldPoint.y,
                worldPoint.z,
                1
            )
            let local = SIMD3<Float>(local4.x, local4.y, local4.z)

            let margin: Float = 0.10
            guard
                abs(local.x) <= faceWidth / 2 + margin,
                abs(local.y) <= faceHeight / 2 + margin
            else { return nil }

            return (worldPoint, local)
        }

        private func updateTracks(with observations: [DetectionObservation]) {
            for index in tracks.indices {
                tracks[index].seenThisFrame = false
            }

            let association = Float(model.associationCm / 100.0)

            for observation in observations {
                var bestIndex: Int?
                var bestDistance = Float.greatestFiniteMagnitude

                for index in tracks.indices {
                    if tracks[index].seenThisFrame { continue }
                    if frameCounter - tracks[index].lastFrame > 40 { continue }

                    let distance = simd_distance(
                        tracks[index].localXY,
                        observation.localXY
                    )

                    let sameKind =
                        tracks[index].kind == observation.kind ||
                        observation.kind == .orange

                    if sameKind && distance < bestDistance {
                        bestDistance = distance
                        bestIndex = index
                    }
                }

                if let index = bestIndex, bestDistance < association {
                    tracks[index].rays.append(observation.ray)
                    if tracks[index].rays.count > 30 {
                        tracks[index].rays.removeFirst()
                    }
                    tracks[index].localXY = observation.localXY
                    tracks[index].lastFrame = frameCounter
                    tracks[index].seenThisFrame = true

                    if observation.kind == .orange {
                        tracks[index].kind = .orange
                    }

                    evaluateTrack(at: index)
                } else {
                    tracks.append(
                        MicroTrack(
                            kind: observation.kind,
                            rays: [observation.ray],
                            localXY: observation.localXY,
                            lastFrame: frameCounter,
                            seenThisFrame: true
                        )
                    )
                }
            }

            tracks.removeAll {
                $0.state != .confirmed &&
                frameCounter - $0.lastFrame > 50
            }

            for index in tracks.indices {
                evaluateTrack(at: index)
            }

            renderMicros()
            publishTrackStats()
        }

        private func evaluateTrack(at index: Int) {
            guard tracks.indices.contains(index), let faceTransform else { return }

            let minBaseline = Float(model.minBaselineCm / 100.0)
            let delta = Float(model.planeDeltaCm / 100.0)

            tracks[index].baseline = maximumBaseline(tracks[index].rays)

            if let result = triangulate(tracks[index].rays) {
                tracks[index].worldPoint = result.point
                tracks[index].residual = result.residual

                let offset = Float(model.planeOffsetCm / 100.0)
                let planeOrigin4 = faceTransform * SIMD4<Float>(0, 0, offset, 1)
                let planeOrigin = SIMD3<Float>(
                    planeOrigin4.x,
                    planeOrigin4.y,
                    planeOrigin4.z
                )
                let normal = simd_normalize(faceTransform.zAxis)

                tracks[index].depthError = abs(
                    simd_dot(result.point - planeOrigin, normal)
                )
            }

            let enoughGeometry =
                tracks[index].rays.count >= 4 &&
                tracks[index].baseline >= minBaseline

            let residualLimit = max(0.10, delta * 1.5)

            if enoughGeometry &&
                tracks[index].depthError <= delta &&
                tracks[index].residual <= residualLimit
            {
                tracks[index].state = .confirmed
            } else if enoughGeometry &&
                        tracks[index].depthError > delta * 1.5
            {
                tracks[index].state = .rejected
            } else {
                tracks[index].state = .provisional
            }
        }

        private func triangulate(
            _ rays: [RayObservation]
        ) -> (point: SIMD3<Float>, residual: Float)? {
            guard rays.count >= 2 else { return nil }

            var A = simd_float3x3(columns: (SIMD3<Float>(repeating: 0), SIMD3<Float>(repeating: 0), SIMD3<Float>(repeating: 0)))
            var b = SIMD3<Float>(repeating: 0)
            let identity = matrix_identity_float3x3

            for ray in rays {
                let d = simd_normalize(ray.direction)
                let outer = simd_float3x3(
                    columns: (d * d.x, d * d.y, d * d.z)
                )
                let M = identity - outer
                A += M
                b += M * ray.origin
            }

            let determinant = simd_determinant(A)
            guard abs(determinant) > 1e-7 else { return nil }

            let point = simd_inverse(A) * b

            var sumSquared: Float = 0
            for ray in rays {
                let d = simd_normalize(ray.direction)
                let v = point - ray.origin
                let perpendicular = v - d * simd_dot(v, d)
                sumSquared += simd_length_squared(perpendicular)
            }

            return (
                point,
                sqrt(sumSquared / Float(rays.count))
            )
        }

        private func maximumBaseline(_ rays: [RayObservation]) -> Float {
            var result: Float = 0

            for i in 0..<rays.count {
                for j in (i + 1)..<rays.count {
                    result = max(
                        result,
                        simd_distance(rays[i].origin, rays[j].origin)
                    )
                }
            }

            return result
        }

        private func renderMicros() {
            guard let root = microAnchor else { return }
            root.children.removeAll()

            for track in tracks {
                guard let point = track.worldPoint else { continue }

                let radius: Float = track.state == .confirmed ? 0.018 : 0.012
                let mesh = MeshResource.generateSphere(radius: radius)

                var material = SimpleMaterial()
                let color: UIColor

                if track.kind == .orange {
                    color = .systemCyan
                } else {
                    switch track.state {
                    case .confirmed: color = .systemGreen
                    case .provisional: color = .systemOrange
                    case .rejected: color = .systemRed
                    }
                }

                material.color = .init(tint: color, texture: nil)
                let entity = ModelEntity(mesh: mesh, materials: [material])
                entity.position = point
                root.addChild(entity)
            }
        }

        private func publishTrackStats() {
            let confirmed = tracks.filter { $0.state == .confirmed }.count
            let provisional = tracks.filter { $0.state == .provisional }.count
            let rejected = tracks.filter { $0.state == .rejected }.count

            Task { @MainActor in
                model.confirmedMicros = confirmed
                model.provisionalMicros = provisional
                model.rejectedMicros = rejected
            }
        }
    }
}

// MARK: - Reconstruction data

private struct DetectionObservation {
    var kind: CapsuleDetection.Kind
    var ray: RayObservation
    var localXY: SIMD2<Float>
}

private struct RayObservation {
    var origin: SIMD3<Float>
    var direction: SIMD3<Float>
}

private enum TrackState: Equatable {
    case provisional
    case confirmed
    case rejected
}

private struct MicroTrack {
    var kind: CapsuleDetection.Kind
    var rays: [RayObservation]
    var localXY: SIMD2<Float>
    var lastFrame: Int
    var seenThisFrame: Bool

    var worldPoint: SIMD3<Float>? = nil
    var depthError: Float = .greatestFiniteMagnitude
    var residual: Float = .greatestFiniteMagnitude
    var baseline: Float = 0
    var state: TrackState = .provisional
}

private extension ARCamera.TrackingState.Reason {
    var description: String {
        switch self {
        case .initializing: return "initialisation"
        case .excessiveMotion: return "mouvement trop rapide"
        case .insufficientFeatures: return "pas assez de détails visuels"
        case .relocalizing: return "relocalisation"
        @unknown default: return "raison inconnue"
        }
    }
}

private extension simd_float4x4 {
    var translation: SIMD3<Float> {
        SIMD3<Float>(columns.3.x, columns.3.y, columns.3.z)
    }

    var zAxis: SIMD3<Float> {
        SIMD3<Float>(columns.2.x, columns.2.y, columns.2.z)
    }
}
