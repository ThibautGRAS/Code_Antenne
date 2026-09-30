import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: ScanModel
    @State private var showSettings = false

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
                            Stepper("\(model.associationCm, specifier: "%.0f") cm", value: $model.associationCm, in: 3...30, step: 1)
                        }
                        LabeledContent("Baseline mini") {
                            Stepper("\(model.minBaselineCm, specifier: "%.0f") cm", value: $model.minBaselineCm, in: 5...100, step: 5)
                        }
                    }

                    Section {
                        Text("Le rectangle est verrouillé dès que les quatre ArUco ont été vus au moins une fois. Ils n’ont pas besoin d’être visibles simultanément.")
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
                Spacer()
                Text(model.faceLocked ? "FACE VERROUILLÉE" : "ACQUISITION")
                    .font(.caption2.bold())
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(model.faceLocked ? Color.green.opacity(0.22) : Color.orange.opacity(0.22))
                    .clipShape(Capsule())
            }

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
        }
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var bottomPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(model.status)
                .font(.caption)
                .lineLimit(3)

            if let delta = model.meanCenterDeltaMm, model.centerMode == .compare {
                Text("Écart centroïde / contour : \(delta, specifier: "%.1f") mm")
                    .font(.caption2)
                    .foregroundStyle(.yellow)
            }

            HStack(spacing: 8) {
                Button {
                    model.isScanning.toggle()
                } label: {
                    Label(model.isScanning ? "Arrêter" : "Scanner", systemImage: model.isScanning ? "stop.fill" : "viewfinder")
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
            }

            HStack(spacing: 10) {
                legend(.green, "dans plan")
                legend(.orange, "provisoire")
                legend(.red, "hors plan")
                legend(.cyan, "orange")
            }
        }
        .padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
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
