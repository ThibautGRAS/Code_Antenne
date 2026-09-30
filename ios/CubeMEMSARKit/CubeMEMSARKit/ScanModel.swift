import Foundation
import SwiftUI

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

    @Published var confirmedMicros = 0
    @Published var provisionalMicros = 0
    @Published var rejectedMicros = 0
    @Published var meanCenterDeltaMm: Double? = nil

    @Published var markerSizeCm: Double = 8.0
    @Published var planeOffsetCm: Double = 3.0
    @Published var planeDeltaCm: Double = 8.0
    @Published var whiteThreshold: Double = 0.82
    @Published var minBaselineCm: Double = 20.0
    @Published var associationCm: Double = 10.0
    @Published var centerMode: CapsuleCenterMode = .compare

    @Published var resetToken = UUID()

    func reset() {
        resetToken = UUID()
        faceLocked = false
        visibleMarkerIDs = []
        mappedMarkerIDs = []
        confirmedMicros = 0
        provisionalMicros = 0
        rejectedMicros = 0
        meanCenterDeltaMm = nil
        status = "Scan réinitialisé."
    }
}
