import Foundation
import SwiftUI

enum ReferenceQuality: String {
    case acquiring = "ACQUISITION"
    case good = "REPÈRE OK"
    case watch = "À RECALER"
    case poor = "RECALAGE CONSEILLÉ"
}

enum CapsuleCenterMode: String, CaseIterable, Identifiable {
    case centroid = "Centroïde"
    case contour = "Contour"
    case compare = "Comparer"

    var id: String { rawValue }
}

final class ScanModel: ObservableObject {
    @Published var isScanning = false
    @Published var status = "Prêt. Démarre le scan puis montre les ArUco un par un."
    @Published var visibleMarkerIDs: Set<Int> = []
    @Published var mappedMarkerIDs: Set<Int> = []
    @Published var faceLocked = false
    @Published var referenceQuality: ReferenceQuality = .acquiring
    @Published var distanceSinceRecalibrationM: Double = 0
    @Published var lastRecalibrationErrorMm: Double? = nil
    @Published var recalibrationCount = 0

    @Published var confirmedMicros = 0
    @Published var provisionalMicros = 0
    @Published var rejectedMicros = 0
    @Published var meanCenterDeltaMm: Double? = nil
    @Published var sizeRejectedThisFrame = 0

    @Published var markerSizeCm: Double = 8.0
    @Published var planeOffsetCm: Double = 3.0
    @Published var planeDeltaCm: Double = 3.0
    @Published var whiteThreshold: Double = 0.82
    @Published var minBaselineCm: Double = 30.0
    @Published var associationCm: Double = 4.5
    @Published var capsuleDiameterMm: Double = 30.0
    @Published var capsuleSizeTolerancePct: Double = 30.0
    @Published var minRays: Int = 7
    @Published var maxUncertaintyMm: Double = 8.0
    /// Capsule rays are suspended beyond this distance walked since the last ArUco recalibration.
    @Published var maxTravelSinceRecalM: Double = 1.5
    @Published var centerMode: CapsuleCenterMode = .compare

    // Test mode without the real antenna: virtual face placed in front of the phone,
    // synthetic detections from the real ARKit pose, live score against ground truth.
    @Published var virtualAntenna = false
    @Published var virtualFaceSizeM: Double = 2.0
    @Published var virtualDistractors = true
    @Published var virtualScore: String? = nil

    @Published var resetToken = UUID()

    func reset() {
        resetToken = UUID()
        faceLocked = false
        referenceQuality = .acquiring
        distanceSinceRecalibrationM = 0
        lastRecalibrationErrorMm = nil
        recalibrationCount = 0
        visibleMarkerIDs = []
        mappedMarkerIDs = []
        confirmedMicros = 0
        provisionalMicros = 0
        rejectedMicros = 0
        meanCenterDeltaMm = nil
        sizeRejectedThisFrame = 0
        virtualScore = nil
        status = "Scan réinitialisé."
    }
}
