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
        private var markerTransforms: [Int: simd_float4x4] = [:]
        private var markerLocalTransforms: [Int: simd_float4x4] = [:]
        private var markerVisuals: [Int: AnchorEntity] = [:]

        private var faceTransform: simd_float4x4?
        private var faceWidth: Float = 2.0
        private var faceHeight: Float = 2.0
        private var faceAnchor: AnchorEntity?
        private var microAnchor: AnchorEntity?

        private var reconstructor = TrackReconstructor()
        private let recorder = ScanRecorder()
        /// Export number of each confirmed track (track index → number), refreshed every update.
        private var numberByTrack: [Int: Int] = [:]
        private var labelMeshes: [Int: MeshResource] = [:]
        private lazy var confirmedSphere = MeshResource.generateSphere(radius: 0.018)
        private lazy var candidateSphere = MeshResource.generateSphere(radius: 0.012)
        private var frameCounter = 0
        private var lastDetectionTime: TimeInterval = 0
        private var detectionRunning = false
        private var lastCameraTransform: simd_float4x4?
        private var lastCameraTimestamp: TimeInterval?
        private var lastReferenceCameraPosition: SIMD3<Float>?
        private var distanceSinceRecalibration: Float = 0

        private var lastResetToken: UUID
        private var lastMarkerSizeCm: Double
        private var lastVirtualConfig: String

        // "Antenne virtuelle" test mode.
        private var virtualAntenna: VirtualAntenna?
        private var virtualAnchor: AnchorEntity?
        private var virtualRNG = SplitMix64(seed: 7)

        init(model: ScanModel) {
            self.model = model
            self.lastResetToken = model.resetToken
            self.lastMarkerSizeCm = model.markerSizeCm
            self.lastVirtualConfig = Self.virtualConfig(model)
            super.init()
        }

        private static func virtualConfig(_ model: ScanModel) -> String {
            "\(model.virtualAntenna)-\(model.virtualFaceSizeM)-\(model.virtualDistractors)"
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
                return
            }

            faceAnchor?.findEntity(named: "faceAxes")?.isEnabled = model.showFaceAxes

            if model.isRecording != recorder.isRecording {
                toggleRecording()
            }

            let virtualConfig = Self.virtualConfig(model)
            if virtualConfig != lastVirtualConfig {
                lastVirtualConfig = virtualConfig
                resetAll()
            }
        }

        private func resetAll() {
            markerCenters.removeAll()
            markerTransforms.removeAll()
            markerLocalTransforms.removeAll()
            reconstructor.reset()
            numberByTrack.removeAll()
            frameCounter = 0
            lastCameraTransform = nil
            lastCameraTimestamp = nil
            lastReferenceCameraPosition = nil
            distanceSinceRecalibration = 0
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

            if let virtualAnchor {
                arView?.scene.removeAnchor(virtualAnchor)
            }
            virtualAnchor = nil
            virtualAntenna = nil

            microAnchor?.children.removeAll()
            startSession(resetTracking: true)

            Task { @MainActor in
                model.visibleMarkerIDs = []
                model.mappedMarkerIDs = []
                model.faceLocked = false
                model.referenceQuality = .acquiring
                model.distanceSinceRecalibrationM = 0
                model.lastRecalibrationErrorMm = nil
                model.recalibrationCount = 0
                model.confirmedMicros = 0
                model.provisionalMicros = 0
                model.rejectedMicros = 0
                model.meanCenterDeltaMm = nil
                model.sizeRejectedThisFrame = 0
                model.virtualScore = nil
                model.virtualCapsuleCount = 0
                model.status = model.virtualAntenna
                    ? "Repère AR réinitialisé. Lance le scan : l'antenne virtuelle sera posée devant toi."
                    : "Repère AR réinitialisé. Montre les ArUco un par un."
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

            if recorder.isRecording {
                var markers: [Int: simd_float4x4] = [:]
                for anchor in frame.anchors {
                    guard let image = anchor as? ARImageAnchor, image.isTracked,
                          let id = markerID(from: image.referenceImage.name) else { continue }
                    markers[id] = image.transform
                }
                if recorder.record(
                    frame: frame,
                    face: faceTransform,
                    faceSize: SIMD2<Float>(faceWidth, faceHeight),
                    planeOffset: Float(model.planeOffsetCm / 100.0),
                    markers: markers
                ) {
                    let count = recorder.frameCount
                    Task { @MainActor in model.recordedFrames = count }
                }
            }

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

            updateReferenceTravel(frame)
            let referenceQuality = currentReferenceQuality(trackingUsable: trackingUsable)

            Task { @MainActor in
                model.visibleMarkerIDs = visible
                model.referenceQuality = faceTransform == nil ? .acquiring : referenceQuality
                model.distanceSinceRecalibrationM = Double(distanceSinceRecalibration)

                switch frame.camera.trackingState {
                case .normal:
                    if model.isScanning {
                        if faceTransform == nil {
                            model.status = model.virtualAntenna
                                ? "Tracking AR OK. Vise devant toi : l'antenne virtuelle va être posée."
                                : "Tracking AR OK. Parcours les quatre ArUco ; ils sont mémorisés."
                        } else if model.virtualAntenna {
                            model.status = tooFast
                                ? "Mouvement rapide : détection suspendue."
                                : "Antenne virtuelle : déplace-toi doucement et latéralement pour trianguler."
                        } else if !visible.isEmpty {
                            model.status = "ArUco revu : recalage doux du repère cube en cours."
                        } else if tooFast {
                            model.status = "Mouvement rapide : rectangle conservé, détection micros temporairement suspendue."
                        } else if referenceQuality == .poor {
                            model.status = "Détection en pause : repasse quelques secondes sur un ArUco pour recaler le repère."
                        } else if referenceQuality == .watch {
                            model.status = "Repère encore exploitable ; repasse bientôt sur un ArUco pour limiter la dérive."
                        } else {
                            model.status = "Face verrouillée. Déplace-toi doucement et latéralement pour trianguler les capsules."
                        }
                    }
                case .limited(let reason):
                    model.status = "Tracking AR limité : \(reason.description). Un recalage ArUco sera conseillé."
                case .notAvailable:
                    model.status = "Tracking AR indisponible."
                @unknown default:
                    break
                }
            }

            if model.virtualAntenna, model.isScanning, faceTransform == nil, trackingUsable {
                placeVirtualAntenna(frame)
            }

            guard model.isScanning, faceTransform != nil, trackingUsable, !tooFast else { return }

            // Simulation (tests): beyond ~1.5 m walked since the last ArUco, ARKit drift makes new
            // rays inconsistent with older ones. Wait for a recalibration instead of adding them.
            if !model.virtualAntenna,
               distanceSinceRecalibration > Float(model.maxTravelSinceRecalM) {
                return
            }

            let now = frame.timestamp
            guard now - lastDetectionTime > 0.20, !detectionRunning else { return }
            lastDetectionTime = now

            if model.virtualAntenna, let virtualAntenna {
                consumeVirtual(antenna: virtualAntenna, frame: frame)
                return
            }

            detectionRunning = true

            let pixelBuffer = frame.capturedImage
            let centerMode = model.centerMode
            let threshold = model.whiteThreshold
            let target = model.detectionMode
            let stickerColor = model.stickerColor

            detectorQueue.async { [weak self] in
                guard let self else { return }

                let detections = CapsuleDetector.detect(
                    pixelBuffer: pixelBuffer,
                    mode: centerMode,
                    whiteThreshold: threshold,
                    target: target,
                    stickerColor: stickerColor
                )

                DispatchQueue.main.async { [weak self] in
                    guard let self else { return }
                    self.consume(detections: detections, frame: frame)
                    self.detectionRunning = false
                }
            }
        }

        private func updateReferenceTravel(_ frame: ARFrame) {
            let current = frame.camera.transform.translation
            defer { lastReferenceCameraPosition = current }

            guard faceTransform != nil, let previous = lastReferenceCameraPosition else { return }

            let step = simd_distance(previous, current)
            // Ignore impossible frame-to-frame jumps caused by AR relocalization.
            if step < 0.25 {
                distanceSinceRecalibration += step
            }
        }

        private func currentReferenceQuality(trackingUsable: Bool) -> ReferenceQuality {
            guard faceTransform != nil else { return .acquiring }
            guard trackingUsable else { return .poor }

            let limit = Float(model.maxTravelSinceRecalM)
            if distanceSinceRecalibration < 0.66 * limit {
                return .good
            } else if distanceSinceRecalibration <= limit {
                return .watch
            } else {
                return .poor
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
            guard model.isScanning, !model.virtualAntenna else { return }

            var observed: [Int: simd_float4x4] = [:]

            for anchor in anchors {
                guard
                    let image = anchor as? ARImageAnchor,
                    image.isTracked,
                    let id = markerID(from: image.referenceImage.name)
                else { continue }

                observed[id] = image.transform
                markerTransforms[id] = image.transform

                let p = image.transform.translation

                if faceTransform == nil {
                    if let old = markerCenters[id] {
                        markerCenters[id] = old * 0.75 + p * 0.25
                    } else {
                        markerCenters[id] = p
                    }
                    updateMarkerVisual(id: id, position: markerCenters[id] ?? p)
                }
            }

            if faceTransform == nil {
                Task { @MainActor in
                    model.mappedMarkerIDs = Set(markerCenters.keys)
                }
                lockFaceIfReady()
            } else if !observed.isEmpty {
                softRecalibrate(using: observed)
            }
        }

        private func softRecalibrate(using observed: [Int: simd_float4x4]) {
            guard
                let oldFace = faceTransform,
                let outcome = FaceRecalibration.soft(
                    face: oldFace,
                    observed: observed,
                    markerLocal: markerLocalTransforms
                )
            else { return }

            switch outcome {
            case let .rejected(translationJump, rotationJump):
                Task { @MainActor in
                    model.referenceQuality = .poor
                    model.status = String(
                        format: "ArUco incohérent (écart %.0f mm / %.1f°) : correction ignorée.",
                        translationJump * 1000,
                        rotationJump * 180 / .pi
                    )
                }

            case let .applied(newFace, delta, rmsMm, markerCount):
                faceTransform = newFace
                if let face = currentFace() {
                    reconstructor.faceDidMove(to: face)
                }

                if let faceAnchor {
                    faceAnchor.setTransformMatrix(newFace, relativeTo: nil)
                }

                // Keep marker visuals and stored corner centers in the corrected frame.
                for id in markerCenters.keys {
                    if let p = markerCenters[id] {
                        let corrected = transformPoint(delta, p)
                        markerCenters[id] = corrected
                        updateMarkerVisual(id: id, position: corrected)
                    }
                }
                for (id, markerWorld) in observed {
                    markerCenters[id] = markerWorld.translation
                    updateMarkerVisual(id: id, position: markerWorld.translation)
                }

                distanceSinceRecalibration = 0
                lastReferenceCameraPosition = nil

                renderMicros()

                Task { @MainActor in
                    model.referenceQuality = .good
                    model.distanceSinceRecalibrationM = 0
                    model.lastRecalibrationErrorMm = Double(rmsMm)
                    model.recalibrationCount += 1
                    model.status = String(
                        format: "Repère recalé avec %d ArUco — résidu %.1f mm.",
                        markerCount,
                        rmsMm
                    )
                }
            }
        }

        private func transformPoint(
            _ transform: simd_float4x4,
            _ point: SIMD3<Float>
        ) -> SIMD3<Float> {
            let result = transform * SIMD4<Float>(point.x, point.y, point.z, 1)
            return SIMD3<Float>(result.x, result.y, result.z)
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

            markerLocalTransforms.removeAll()
            for (id, markerWorld) in markerTransforms {
                markerLocalTransforms[id] = simd_inverse(transform) * markerWorld
            }

            distanceSinceRecalibration = 0
            lastReferenceCameraPosition = nil
            renderLockedFace()

            Task { @MainActor in
                model.faceLocked = true
                model.referenceQuality = .good
                model.distanceSinceRecalibrationM = 0
                model.lastRecalibrationErrorMm = 0
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

            anchor.addChild(makeFaceAxes())

            arView.scene.addAnchor(anchor)
        }

        /// X (red), Y (green), Z (blue) arrows of the export frame, at the face origin.
        private func makeFaceAxes() -> Entity {
            let axes = Entity()
            axes.name = "faceAxes"
            axes.isEnabled = model.showFaceAxes

            let length: Float = 0.3
            let thickness: Float = 0.008
            let specs: [(axis: SIMD3<Float>, color: UIColor, name: String)] = [
                (SIMD3<Float>(1, 0, 0), .systemRed, "X"),
                (SIMD3<Float>(0, 1, 0), .systemGreen, "Y"),
                (SIMD3<Float>(0, 0, 1), .systemBlue, "Z")
            ]

            for spec in specs {
                let material = UnlitMaterial(color: spec.color)
                let size = spec.axis * length + (SIMD3<Float>(repeating: 1) - spec.axis) * thickness

                let shaft = ModelEntity(mesh: .generateBox(size: size), materials: [material])
                shaft.position = spec.axis * (length / 2)
                axes.addChild(shaft)

                let tip = ModelEntity(mesh: .generateSphere(radius: 0.016), materials: [material])
                tip.position = spec.axis * length
                axes.addChild(tip)

                let label = ModelEntity(
                    mesh: .generateText(
                        spec.name,
                        extrusionDepth: 0.002,
                        font: .boldSystemFont(ofSize: 0.06),
                        containerFrame: .zero,
                        alignment: .left,
                        lineBreakMode: .byClipping
                    ),
                    materials: [material]
                )
                label.position = spec.axis * (length + 0.03)
                axes.addChild(label)
            }

            return axes
        }

        // MARK: - Diagnostic recording

        private func toggleRecording() {
            if model.isRecording {
                do {
                    try recorder.start(meta: recordingMeta())
                    Task { @MainActor in
                        model.recordedFrames = 0
                        model.recordingMessage = "Enregistrement en cours : une image toutes les 0,5 s."
                    }
                } catch {
                    Task { @MainActor in
                        model.isRecording = false
                        model.recordingMessage = "Enregistrement impossible : \(error.localizedDescription)"
                    }
                }
            } else {
                let count = recorder.frameCount
                Task { @MainActor in model.recordingMessage = "Préparation du fichier zip…" }
                recorder.stop { [weak self] result in
                    guard let self else { return }
                    switch result {
                    case .success(let url):
                        let size = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
                        self.model.lastRecordingURL = url
                        self.model.recordingMessage = String(
                            format: "Enregistrement prêt : %d images, %.0f Mo.",
                            count, Double(size) / 1_000_000
                        )
                    case .failure(let error):
                        self.model.recordingMessage = "Échec de l'enregistrement : \(error.localizedDescription)"
                    }
                }
            }
        }

        /// Settings snapshot stored with the recording, to replay with the same parameters.
        private func recordingMeta() -> [String: Any] {
            let info = Bundle.main.infoDictionary ?? [:]
            return [
                "format": "CubeMEMS-recording-1",
                "app": "\(info["CFBundleShortVersionString"] ?? "?") (\(info["CFBundleVersion"] ?? "?"))",
                "date": ISO8601DateFormatter().string(from: Date()),
                "device": UIDevice.current.model,
                "system": UIDevice.current.systemVersion,
                "intervalSeconds": recorder.interval,
                "virtualAntenna": model.virtualAntenna,
                "settings": [
                    "markerSizeCm": model.markerSizeCm,
                    "planeOffsetCm": model.planeOffsetCm,
                    "planeDeltaCm": model.planeDeltaCm,
                    "capsuleDiameterMm": model.capsuleDiameterMm,
                    "detectionMode": model.detectionMode == .colorSticker ? "sticker" : "white",
                    "stickerColor": "\(model.stickerColor)",
                    "stickerDiameterMm": model.stickerDiameterMm,
                    "capsuleSizeTolerancePct": model.capsuleSizeTolerancePct,
                    "whiteThreshold": model.whiteThreshold,
                    "associationCm": model.associationCm,
                    "minRays": model.minRays,
                    "minBaselineCm": model.minBaselineCm,
                    "maxUncertaintyMm": model.maxUncertaintyMm,
                    "maxTravelSinceRecalM": model.maxTravelSinceRecalM,
                    "expectedMicrophonesPerFace": model.expectedMicrophonesPerFace,
                    "microphonesPerColumn": model.microphonesPerColumn
                ]
            ]
        }

        // MARK: - Virtual antenna (test without the real antenna)

        /// Places a virtual face 1.6 m in front of the phone, vertical, facing the operator.
        private func placeVirtualAntenna(_ frame: ARFrame) {
            let camera = frame.camera.transform
            var forward = -camera.zAxis
            forward.y = 0
            // Phone pointing at the floor or the ceiling: wait for a usable heading.
            guard simd_length(forward) > 0.2 else { return }
            forward = simd_normalize(forward)

            let size = Float(model.virtualFaceSizeM)
            let center = camera.translation + forward * 1.6
            let normal = -forward
            let up = SIMD3<Float>(0, 1, 0)
            let right = simd_normalize(simd_cross(up, normal))

            var transform = matrix_identity_float4x4
            transform.columns.0 = SIMD4<Float>(right.x, right.y, right.z, 0)
            transform.columns.1 = SIMD4<Float>(up.x, up.y, up.z, 0)
            transform.columns.2 = SIMD4<Float>(normal.x, normal.y, normal.z, 0)
            transform.columns.3 = SIMD4<Float>(center.x, center.y, center.z, 1)

            virtualRNG = SplitMix64(seed: 7)
            let antenna = VirtualAntenna.make(
                faceSize: size,
                planeOffset: Float(model.planeOffsetCm / 100.0),
                capsuleDiameter: Float(model.capsuleDiameterMm / 1000.0),
                backFace: model.virtualDistractors,
                backFaceDepth: size,
                clutterCount: model.virtualDistractors ? 60 : 0,
                rng: &virtualRNG
            )

            virtualAntenna = antenna
            faceTransform = transform
            faceWidth = size
            faceHeight = size
            markerLocalTransforms.removeAll()
            distanceSinceRecalibration = 0
            lastReferenceCameraPosition = nil

            renderLockedFace()
            renderVirtualAntenna(antenna, face: transform)

            let capsuleCount = antenna.capsulePositions.count

            Task { @MainActor in
                model.faceLocked = true
                model.virtualCapsuleCount = capsuleCount
                model.mappedMarkerIDs = [0, 1, 2, 3]
                model.referenceQuality = .good
                model.distanceSinceRecalibrationM = 0
                model.status = String(
                    format: "Antenne virtuelle posée à 1,6 m (face %.0f m). Déplace-toi latéralement pour trianguler.",
                    size
                )
            }
        }

        private func renderVirtualAntenna(_ antenna: VirtualAntenna, face: simd_float4x4) {
            guard let arView else { return }

            if let old = virtualAnchor {
                arView.scene.removeAnchor(old)
            }

            let anchor = AnchorEntity(world: face)

            var capsuleMaterial = SimpleMaterial()
            capsuleMaterial.color = .init(tint: .white, texture: nil)
            var backMaterial = SimpleMaterial()
            backMaterial.color = .init(tint: .lightGray, texture: nil)

            for target in antenna.targets {
                let radius = max(0.006, target.diameter / 2)
                let material = target.kind == .backCapsule ? backMaterial : capsuleMaterial
                let sphere = ModelEntity(mesh: .generateSphere(radius: radius), materials: [material])
                sphere.position = target.local
                anchor.addChild(sphere)
            }

            arView.scene.addAnchor(anchor)
            virtualAnchor = anchor
        }

        /// Same chain as consume(detections:frame:) with synthetic detections from the real ARKit pose.
        private func consumeVirtual(antenna: VirtualAntenna, frame: ARFrame) {
            guard let face = currentFace() else { return }

            let camera = PinholeCamera(
                transform: frame.camera.transform,
                intrinsics: frame.camera.intrinsics,
                imageSize: SIMD2<Float>(
                    Float(CVPixelBufferGetWidth(frame.capturedImage)),
                    Float(CVPixelBufferGetHeight(frame.capturedImage))
                )
            )
            let detections = antenna.detections(face: face, camera: camera, model: DetectorModel(), rng: &virtualRNG)

            let cameraFromWorld = simd_inverse(frame.camera.transform)
            let focalPixels = 0.5 * (camera.intrinsics.columns.0.x + camera.intrinsics.columns.1.y)
            var observations: [DetectionObservation] = []
            var sizeRejected = 0

            for detection in detections {
                guard let nominal = face.nominalIntersection(
                    origin: detection.origin,
                    direction: detection.direction
                ) else { continue }

                guard CapsuleSizeFilter.passes(
                    observedDiameterPixels: detection.diameterPixels,
                    physicalDiameter: Float(model.capsuleDiameterMm / 1000.0),
                    depth: abs(cameraFromWorld.transformPoint(nominal.world).z),
                    focalPixels: focalPixels,
                    tolerance: Float(model.capsuleSizeTolerancePct / 100.0)
                ) else {
                    sizeRejected += 1
                    continue
                }

                observations.append(
                    DetectionObservation(
                        kind: .white,
                        ray: RayObservation(origin: detection.origin, direction: detection.direction),
                        localXY: SIMD2<Float>(nominal.local.x, nominal.local.y)
                    )
                )
            }

            updateTracks(with: observations)

            let score = ReconstructionScorer.score(
                tracks: reconstructor.tracks,
                capsules: antenna.capsulePositions,
                face: face
            )
            let scoreText = String(
                format: "Vérité terrain : %d/%d capsules · %d doublons · %d faux · %d imprécis · RMS %.1f mm",
                score.matchedCapsules, score.capsules, score.duplicates,
                score.falseConfirmed, score.inaccurate, score.rmsErrorMm
            )

            Task { @MainActor in
                model.sizeRejectedThisFrame = sizeRejected
                model.meanCenterDeltaMm = nil
                model.virtualScore = scoreText
            }
        }

        // MARK: - Capsule reconstruction

        private func currentFace() -> FaceGeometry? {
            guard let faceTransform else { return nil }
            return FaceGeometry(
                transform: faceTransform,
                width: faceWidth,
                height: faceHeight,
                planeOffset: Float(model.planeOffsetCm / 100.0)
            )
        }

        private func reconstructionParameters() -> ReconstructionParameters {
            var parameters = ReconstructionParameters()
            parameters.associationRadius = Float(model.associationCm / 100.0)
            parameters.minBaseline = Float(model.minBaselineCm / 100.0)
            parameters.planeTolerance = Float(model.planeDeltaCm / 100.0)
            parameters.minRays = model.minRays
            parameters.maxUncertainty = Float(model.maxUncertaintyMm / 1000.0)
            return parameters
        }

        private func consume(detections: [CapsuleDetection], frame: ARFrame) {
            guard
                let arView,
                let face = currentFace()
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
            var sizeRejected = 0

            for detection in detections {
                let selectedScreen = screenPoint(
                    imagePixel: detection.selectedPixel,
                    imageWidth: imageWidth,
                    imageHeight: imageHeight,
                    displayTransform: displayTransform,
                    viewport: viewport
                )

                guard let ray = arView.ray(through: selectedScreen) else { continue }
                guard let nominal = face.nominalIntersection(
                    origin: ray.origin,
                    direction: ray.direction
                ) else { continue }

                if detection.kind == .white,
                   !passesPhysicalSizeFilter(
                        detection: detection,
                        worldPoint: nominal.world,
                        frame: frame
                   )
                {
                    sizeRejected += 1
                    continue
                }

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
                        let cPoint = face.nominalIntersection(origin: cRay.origin, direction: cRay.direction),
                        let ePoint = face.nominalIntersection(origin: eRay.origin, direction: eRay.direction)
                    {
                        let delta = simd_distance(cPoint.world, ePoint.world)
                        centerDeltasMm.append(Double(delta * 1000))
                    }
                }

                observations.append(
                    DetectionObservation(
                        kind: detection.kind == .orange ? .orange : .white,
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
                model.sizeRejectedThisFrame = sizeRejected
                model.meanCenterDeltaMm = centerDeltasMm.isEmpty
                    ? nil
                    : centerDeltasMm.reduce(0, +) / Double(centerDeltasMm.count)
            }
        }

        private func passesPhysicalSizeFilter(
            detection: CapsuleDetection,
            worldPoint: SIMD3<Float>,
            frame: ARFrame
        ) -> Bool {
            if detection.kind == .orange {
                return true
            }

            let cameraPoint = simd_inverse(frame.camera.transform).transformPoint(worldPoint)

            let intrinsics = frame.camera.intrinsics
            let focalPixels = 0.5 * (
                intrinsics.columns.0.x +
                intrinsics.columns.1.y
            )

            return CapsuleSizeFilter.passes(
                observedDiameterPixels: Float(detection.diameterPixels),
                physicalDiameter: Float(model.detectedDiameterMm / 1000.0),
                depth: abs(cameraPoint.z),
                focalPixels: focalPixels,
                tolerance: Float(model.capsuleSizeTolerancePct / 100.0)
            )
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

        private func updateTracks(with observations: [DetectionObservation]) {
            guard let face = currentFace() else { return }

            reconstructor.parameters = reconstructionParameters()
            reconstructor.update(with: observations, frame: frameCounter, face: face)

            let numbered = MicrophoneNumbering.number(
                reconstructor.tracks,
                columnGap: Float(model.columnGapCm / 100.0)
            )
            numberByTrack = Dictionary(uniqueKeysWithValues: numbered.map { ($0.trackIndex, $0.number) })

            renderMicros()
            publishTrackStats(numbered)
        }

        private func renderMicros() {
            guard let root = microAnchor else { return }
            root.children.removeAll()

            let showNumbers = model.showMicrophoneNumbers

            for (index, track) in reconstructor.tracks.enumerated() {
                guard let point = track.worldPoint else { continue }

                let mesh = track.state == .confirmed ? confirmedSphere : candidateSphere

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

                if showNumbers,
                   track.state == .confirmed,
                   let number = numberByTrack[index],
                   let faceTransform
                {
                    root.addChild(numberLabel(number, at: point, face: faceTransform))
                }
            }
        }

        /// Export number written in the face plane (readable when facing the grid), next to the sphere.
        private func numberLabel(_ number: Int, at point: SIMD3<Float>, face: simd_float4x4) -> ModelEntity {
            let mesh: MeshResource
            if let cached = labelMeshes[number] {
                mesh = cached
            } else {
                mesh = MeshResource.generateText(
                    "\(number)",
                    extrusionDepth: 0.001,
                    font: .boldSystemFont(ofSize: 0.035),
                    containerFrame: .zero,
                    alignment: .left,
                    lineBreakMode: .byClipping
                )
                labelMeshes[number] = mesh
            }

            let label = ModelEntity(mesh: mesh, materials: [UnlitMaterial(color: .systemYellow)])
            var rotation = face
            rotation.columns.3 = SIMD4<Float>(0, 0, 0, 1)
            label.transform = Transform(matrix: rotation)
            label.position = point + face.rotation * SIMD3<Float>(0.022, 0.008, 0.01)
            return label
        }

        private func publishTrackStats(_ numbered: [NumberedMicrophone]) {
            let confirmed = reconstructor.confirmedCount
            let provisional = reconstructor.provisionalCount
            let rejected = reconstructor.rejectedCount

            Task { @MainActor in
                model.confirmedMicros = confirmed
                model.provisionalMicros = provisional
                model.rejectedMicros = rejected
                model.numberedMicrophones = numbered
            }
        }
    }
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
