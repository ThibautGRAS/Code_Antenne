import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: ScanModel
    @State private var showSettings = false
    @State private var topExpanded = true
    @State private var bottomExpanded = true

    var body: some View {
        ZStack {
            ARScannerView(model: model)
                .ignoresSafeArea()

            VStack(spacing: 10) {
                topPanel
                Spacer()
                bottomPanel
            }
            .padding(.horizontal, 12)
            .padding(.top, 8)
            .padding(.bottom, 10)
        }
        .sheet(isPresented: $showSettings) {
            NavigationStack {
                Form {
                    Section("Géométrie") {
                        LabeledContent("Taille ArUco") {
                            Stepper("\(model.markerSizeCm, specifier: "%.1f") cm", value: $model.markerSizeCm, in: 3...20, step: 0.5)
                        }
                        LabeledContent("Décalage plan micro") {
                            Stepper("\(model.planeOffsetCm, specifier: "%.0f") cm", value: $model.planeOffsetCm, in: -30...30, step: 1)
                        }
                        LabeledContent("Tolérance plan") {
                            Stepper("±\(model.planeDeltaCm, specifier: "%.0f") cm", value: $model.planeDeltaCm, in: 1...30, step: 1)
                        }
                    }

                    Section("Détection capsule") {
                        Picker("Centre utilisé", selection: $model.centerMode) {
                            ForEach(CapsuleCenterMode.allCases) { mode in
                                Text(mode.rawValue).tag(mode)
                            }
                        }
                        LabeledContent("Seuil blanc") {
                            Slider(value: $model.whiteThreshold, in: 0.65...0.95)
                                .frame(width: 150)
                        }
                        LabeledContent("Association") {
                            Stepper("\(model.associationCm, specifier: "%.1f") cm", value: $model.associationCm, in: 2...30, step: 0.5)
                        }
                        LabeledContent("Diamètre capsule") {
                            Stepper("\(model.capsuleDiameterMm, specifier: "%.0f") mm", value: $model.capsuleDiameterMm, in: 10...60, step: 1)
                        }
                        LabeledContent("Tolérance taille") {
                            Stepper("±\(model.capsuleSizeTolerancePct, specifier: "%.0f") %", value: $model.capsuleSizeTolerancePct, in: 20...100, step: 5)
                        }
                        LabeledContent("Baseline mini") {
                            Stepper("\(model.minBaselineCm, specifier: "%.0f") cm", value: $model.minBaselineCm, in: 5...100, step: 5)
                        }
                        LabeledContent("Rayons mini") {
                            Stepper("\(model.minRays)", value: $model.minRays, in: 2...20)
                        }
                        LabeledContent("Incertitude max") {
                            Stepper("\(model.maxUncertaintyMm, specifier: "%.0f") mm", value: $model.maxUncertaintyMm, in: 2...50, step: 1)
                        }
                    }

                    Section("Test sans antenne") {
                        Toggle("Antenne virtuelle", isOn: $model.virtualAntenna)
                        if model.virtualAntenna {
                            Picker("Taille de la face", selection: $model.virtualFaceSizeM) {
                                Text("2 m").tag(2.0)
                                Text("1 m").tag(1.0)
                            }
                            Toggle("Face arrière + objets blancs", isOn: $model.virtualDistractors)
                        }
                        Text("Une face virtuelle est posée à 1,6 m devant le téléphone au démarrage du scan. Les capsules blanches sont virtuelles mais le suivi ARKit est réel : marche autour comme devant l'antenne. Le score compare les micros verts à la vraie position des capsules. Pas d'ArUco, donc pas de recalage.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Section("Recalage du repère") {
                        LabeledContent("Distance max sans ArUco") {
                            Stepper("\(model.maxTravelSinceRecalM, specifier: "%.1f") m", value: $model.maxTravelSinceRecalM, in: 0.5...10, step: 0.5)
                        }
                        Text("Après le verrouillage, ARKit continue seul. Quand un ArUco réapparaît, sa pose 6-DoF sert à recaler doucement le repère du cube sans effacer les micros déjà reconstruits. Un passage périodique sur un marqueur limite la dérive.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .navigationTitle("Réglages")
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Fermer") { showSettings = false }
                    }
                }
            }
        }
    }

    private var topPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Cube MEMS AR")
                    .font(.headline)
                    .lineLimit(1)
                    .fixedSize()
                if model.virtualAntenna {
                    Text("VIRTUEL")
                        .font(.caption2.bold())
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(Color.purple.opacity(0.6))
                        .clipShape(Capsule())
                }
                Spacer()
                if !model.virtualAntenna {
                    Text(model.referenceQuality.rawValue)
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .background(referenceColor.opacity(0.22))
                        .clipShape(Capsule())
                }
                if !topExpanded {
                    Text("\(model.confirmedMicros) micros")
                        .font(.caption.monospacedDigit())
                }
                collapseButton(expanded: $topExpanded, up: true)
            }

            if topExpanded {
                topDetails
            }
        }
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var topDetails: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                metric("\(model.visibleMarkerIDs.count)", "visibles")
                metric("\(model.mappedMarkerIDs.count)/4", "mappés")
                metric("\(model.confirmedMicros)", "micros")
                metric("±\(Int(model.planeDeltaCm))", "cm plan")
            }

            HStack(spacing: 6) {
                ForEach(0..<4, id: \.self) { id in
                    Text("ID\(id)")
                        .font(.caption2.bold())
                        .foregroundStyle(model.mappedMarkerIDs.contains(id) ? .white : .secondary)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(model.mappedMarkerIDs.contains(id) ? Color.blue.opacity(0.72) : Color.black.opacity(0.36))
                        .clipShape(Capsule())
                }
                Spacer()
            }

            if model.faceLocked && !model.virtualAntenna {
                HStack(spacing: 6) {
                    Circle()
                        .fill(referenceColor)
                        .frame(width: 8, height: 8)

                    Text("\(model.distanceSinceRecalibrationM, specifier: "%.1f") m depuis recalage")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    if let error = model.lastRecalibrationErrorMm {
                        Text("• ε \(error, specifier: "%.1f") mm")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }

                    Spacer()
                }
            }
        }
    }

    private var bottomPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            if bottomExpanded {
                bottomDetails
            }

            HStack(spacing: 8) {
                Button {
                    model.isScanning.toggle()
                } label: {
                    Label(model.isScanning ? "Arrêter" : "Scanner", systemImage: model.isScanning ? "stop.fill" : "viewfinder")
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)

                Button {
                    showSettings = true
                } label: {
                    Image(systemName: "slider.horizontal.3")
                }
                .buttonStyle(.bordered)

                Button(role: .destructive) {
                    model.reset()
                } label: {
                    Image(systemName: "arrow.counterclockwise")
                }
                .buttonStyle(.bordered)

                collapseButton(expanded: $bottomExpanded, up: false)
            }
        }
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var bottomDetails: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(model.status)
                .font(.caption)
                .lineLimit(3)

            if let delta = model.meanCenterDeltaMm, model.centerMode == .compare {
                Text("Écart centroïde / contour : \(delta, specifier: "%.1f") mm")
                    .font(.caption2)
                    .foregroundStyle(.yellow)
            }

            if model.virtualAntenna, let score = model.virtualScore {
                Text(score)
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.purple)
            }

            if model.sizeRejectedThisFrame > 0 {
                Text("Filtre taille physique : \(model.sizeRejectedThisFrame) candidat(s) écarté(s) sur la dernière image.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 10) {
                legend(.green, "dans plan")
                legend(.orange, "provisoire")
                legend(.red, "hors plan")
                legend(.cyan, "orange")
            }
        }
    }

    /// Chevron that folds a panel to free the camera view.
    private func collapseButton(expanded: Binding<Bool>, up: Bool) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                expanded.wrappedValue.toggle()
            }
        } label: {
            Image(systemName: expanded.wrappedValue == up ? "chevron.up" : "chevron.down")
                .font(.caption.bold())
                .frame(width: 28, height: 28)
        }
        .buttonStyle(.bordered)
    }

    private var referenceColor: Color {
        switch model.referenceQuality {
        case .acquiring: return .orange
        case .good: return .green
        case .watch: return .orange
        case .poor: return .red
        }
    }

    private func metric(_ value: String, _ label: String) -> some View {
        VStack(spacing: 1) {
            Text(value).font(.headline.monospacedDigit())
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.22), in: RoundedRectangle(cornerRadius: 9))
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(text).font(.caption2)
        }
    }
}
