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

/// A channel whose position in the real antenna frame is known (meters).
struct ReferencePoint: Identifiable, Codable, Equatable {
    var id = UUID()
    var channel: Int
    var x: Double
    var y: Double
    var z: Double
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

    /// Confirmed microphones in export order (rightmost column first, bottom to top).
    @Published var numberedMicrophones: [NumberedMicrophone] = []
    /// A new column starts where the horizontal gap between microphones exceeds this.
    @Published var columnGapCm: Double = 8.0
    /// Microphones mounted on one face of the real antenna.
    @Published var expectedMicrophonesPerFace = 96
    @Published var showMicrophoneNumbers = true
    /// X/Y/Z arrows of the export frame on the locked face.
    @Published var showFaceAxes = true
    /// Ground-truth capsule count of the virtual antenna (set when it is placed).
    @Published var virtualCapsuleCount = 0

    // Real antenna frame: reference channels (kept between sessions) and export option.
    @Published var referencePoints: [ReferencePoint] = ScanModel.loadReferences() {
        didSet { saveReferences() }
    }
    @Published var useRealFrame = UserDefaults.standard.bool(forKey: "useRealFrame") {
        didSet { UserDefaults.standard.set(useRealFrame, forKey: "useRealFrame") }
    }

    /// Fit of the current microphones onto the reference channels.
    var registration: Result<ReferenceRegistration, ReferenceRegistrationError> {
        var references: [Int: SIMD3<Double>] = [:]
        for point in referencePoints {
            references[point.channel] = SIMD3<Double>(point.x, point.y, point.z)
        }
        return RigidRegistration.register(microphones: numberedMicrophones, references: references)
    }

    private static let referencesKey = "referencePoints"

    private static func loadReferences() -> [ReferencePoint] {
        guard
            let data = UserDefaults.standard.data(forKey: referencesKey),
            let points = try? JSONDecoder().decode([ReferencePoint].self, from: data)
        else { return [] }
        return points
    }

    private func saveReferences() {
        if let data = try? JSONEncoder().encode(referencePoints) {
            UserDefaults.standard.set(data, forKey: Self.referencesKey)
        }
    }

    /// Count the export is checked against.
    var expectedMicrophones: Int {
        virtualAntenna ? virtualCapsuleCount : expectedMicrophonesPerFace
    }
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
        numberedMicrophones = []
        status = "Scan réinitialisé."
    }
}
