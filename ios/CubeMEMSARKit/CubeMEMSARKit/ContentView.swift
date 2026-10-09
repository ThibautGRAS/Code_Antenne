import SwiftUI
import UIKit
import simd

struct ContentView: View {
    @EnvironmentObject private var model: ScanModel
    @State private var showSettings = false
    @State private var topExpanded = true
    @State private var bottomExpanded = true
    @State private var exportFiles: [URL] = []
    @State private var showExport = false
    @State private var exportError: String?
    @State private var confirmIncompleteExport = false
    @State private var markerFiles: [URL] = []
    @State private var showMarkerShare = false

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
            .sheet(isPresented: $showExport) {
                ActivityView(items: exportFiles)
            }
            .alert("Export impossible", isPresented: Binding(
                get: { exportError != nil },
                set: { if !$0 { exportError = nil } }
            )) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(exportError ?? "")
            }
        }
        .sheet(isPresented: $showSettings) {
            NavigationStack {
                Form {
                    Section("Aide · Marqueurs ArUco") {
                        Text("Imprimer les 4 marqueurs à 100 % (taille réelle), vérifier la règle de 100 mm, puis les coller à plat aux coins de la face, vus de face : ID0 en haut à gauche, ID1 en haut à droite, ID2 en bas à droite, ID3 en bas à gauche.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        Button {
                            exportMarkerSheet()
                        } label: {
                            Label("Planche à imprimer (PDF)", systemImage: "printer")
                        }
                    }

                    Section("Géométrie") {
                        stepperRow("Taille ArUco", String(format: "%.1f cm", model.markerSizeCm),
                                   $model.markerSizeCm, 3...20, 0.5)
                        stepperRow("Décalage plan micro", String(format: "%.0f cm", model.planeOffsetCm),
                                   $model.planeOffsetCm, -30...30, 1)
                        stepperRow("Tolérance plan", String(format: "±%.0f cm", model.planeDeltaCm),
                                   $model.planeDeltaCm, 1...30, 1)
                        Toggle("Afficher les axes X/Y/Z", isOn: $model.showFaceAxes)
                        Text("Repère des micros : origine au centre des 4 ArUco, X (rouge) de gauche à droite, Y (vert) vers le haut, Z (bleu) perpendiculaire à la face vers l'opérateur. Le décalage du plan micro est compté sur Z : positif si les capsules sont devant les marqueurs (côté opérateur), négatif si elles sont derrière.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Section("Détection capsule") {
                        Toggle("Détecter des pastilles de couleur", isOn: Binding(
                            get: { model.detectionMode == .colorSticker },
                            set: { model.detectionMode = $0 ? .colorSticker : .whiteCapsule }
                        ))
                        if model.detectionMode == .colorSticker {
                            Picker("Couleur de la pastille", selection: $model.stickerColor) {
                                ForEach(StickerColor.allCases) { color in
                                    Text(color.rawValue).tag(color)
                                }
                            }
                            stepperRow("Diamètre pastille", String(format: "%.0f mm", model.stickerDiameterMm),
                                       $model.stickerDiameterMm, 4...40, 1)
                            Text("Pastille centrée sur chaque capsule de la face scannée uniquement : le fond et les autres faces sont ignorés. La position mesurée est le centre de la pastille.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                        Picker("Centre utilisé", selection: $model.centerMode) {
                            ForEach(CapsuleCenterMode.allCases) { mode in
                                Text(mode.rawValue).tag(mode)
                            }
                        }
                        if model.detectionMode == .whiteCapsule {
                            VStack(alignment: .leading, spacing: 4) {
                                settingLabel("Seuil blanc", String(format: "%.2f", model.whiteThreshold))
                                Slider(value: $model.whiteThreshold, in: 0.65...0.95)
                            }
                        }
                        stepperRow("Association", String(format: "%.1f cm", model.associationCm),
                                   $model.associationCm, 2...30, 0.5)
                        if model.detectionMode == .whiteCapsule {
                            stepperRow("Diamètre capsule", String(format: "%.0f mm", model.capsuleDiameterMm),
                                       $model.capsuleDiameterMm, 10...60, 1)
                        }
                        stepperRow("Tolérance taille", String(format: "±%.0f %%", model.capsuleSizeTolerancePct),
                                   $model.capsuleSizeTolerancePct, 20...100, 5)
                        stepperRow("Baseline mini", String(format: "%.0f cm", model.minBaselineCm),
                                   $model.minBaselineCm, 5...100, 5)
                        stepperRow("Rayons mini", "\(model.minRays)", $model.minRays, 2...20, 1)
                        stepperRow("Incertitude max", String(format: "%.0f mm", model.maxUncertaintyMm),
                                   $model.maxUncertaintyMm, 2...50, 1)
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

                    Section("Export") {
                        stepperRow("Micros attendus par face", "\(model.expectedMicrophonesPerFace)",
                                   $model.expectedMicrophonesPerFace, 1...400, 1)
                        stepperRow("Micros par colonne", "\(model.microphonesPerColumn)",
                                   $model.microphonesPerColumn, 1...100, 1)
                        Toggle("Afficher les numéros en AR", isOn: $model.showMicrophoneNumbers)
                        Toggle("Grille régulière (colonnes × rangs)", isOn: $model.useGridNumbering)
                        Text("Chaque micro prend le numéro de sa case dans une grille de \(model.gridLayout.columns) colonnes × \(model.gridLayout.rows) rangs, ajustée sur les micros trouvés : écartements inégaux et colonnes pas tout à fait droites sont acceptés. Un micro manquant laisse un trou au lieu de décaler les numéros suivants. Les positions exportées restent celles mesurées.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        stepperRow("Écart min entre colonnes", String(format: "%.0f cm", model.columnGapCm),
                                   $model.columnGapCm, 2...50, 1)
                        Text("Numérotation vue de face, grille devant soi : n° 1 = micro en bas à droite, on remonte la colonne de droite, puis la colonne suivante vers la gauche, de bas en haut, etc. Une nouvelle colonne commence quand l'écart horizontal dépasse ce seuil.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Section("Repère réel de l'antenne") {
                        Toggle("Exporter dans le repère réel", isOn: $model.useRealFrame)
                        ForEach($model.referencePoints) { $reference in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text("Voie")
                                    TextField("n°", value: $reference.channel, format: .number)
                                        .keyboardType(.numberPad)
                                        .textFieldStyle(.roundedBorder)
                                        .frame(width: 70)
                                    Spacer()
                                    Text(residualText(channel: reference.channel))
                                        .font(.caption.monospacedDigit())
                                        .foregroundStyle(.secondary)
                                }
                                HStack(spacing: 6) {
                                    coordinateField("X", $reference.x)
                                    coordinateField("Y", $reference.y)
                                    coordinateField("Z", $reference.z)
                                }
                            }
                        }
                        .onDelete { model.referencePoints.remove(atOffsets: $0) }
                        Button {
                            let existing = Set(model.referencePoints.map { $0.channel })
                            for channel in model.cornerChannels where !existing.contains(channel) {
                                model.referencePoints.append(ReferencePoint(channel: channel, x: 0, y: 0, z: 0))
                            }
                        } label: {
                            Label(
                                "Ajouter les 4 coins (" + model.cornerChannels.map(String.init).joined(separator: ", ") + ")",
                                systemImage: "square.dashed"
                            )
                        }
                        Button {
                            let next = (model.referencePoints.map { $0.channel }.max() ?? 0) + 1
                            model.referencePoints.append(ReferencePoint(channel: next, x: 0, y: 0, z: 0))
                        } label: {
                            Label("Ajouter une voie de référence", systemImage: "plus")
                        }
                        Text(registrationSummary)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    Section("Enregistrement (diagnostic)") {
                        Text("Enregistre une image caméra toutes les 0,5 s avec la pose ARKit, pour rejouer le scan sur PC et régler la détection. Démarrer avant le scan, arrêter à la fin. Environ 30 Mo par minute. Les zips (dossier Enregistrements) et les exports CSV (dossier Exports) restent dans l'app : récupérables sur PC par câble, iTunes › iPhone › Partage de fichiers › Cube MEMS AR, ou dans Fichiers › Sur mon iPhone.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        Button {
                            model.isRecording.toggle()
                        } label: {
                            Label(
                                model.isRecording
                                    ? "Arrêter l'enregistrement (\(model.recordedFrames) images)"
                                    : "Démarrer l'enregistrement",
                                systemImage: model.isRecording ? "stop.circle" : "record.circle"
                            )
                        }
                        if let message = model.recordingMessage {
                            Text(message)
                                .font(.footnote)
                        }
                        if let url = model.lastRecordingURL, !model.isRecording {
                            Button {
                                markerFiles = [url]
                                showMarkerShare = true
                            } label: {
                                Label("Partager le dernier enregistrement", systemImage: "square.and.arrow.up")
                            }
                        }
                    }

                    Section("Recalage du repère") {
                        stepperRow("Distance max sans ArUco", String(format: "%.1f m", model.maxTravelSinceRecalM),
                                   $model.maxTravelSinceRecalM, 0.5...10, 0.5)
                        Text("Après le verrouillage, ARKit continue seul. Quand un ArUco réapparaît, sa pose 6-DoF sert à recaler doucement le repère du cube sans effacer les micros déjà reconstruits. Un passage périodique sur un marqueur limite la dérive.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .navigationTitle("Réglages")
                .sheet(isPresented: $showMarkerShare) {
                    ActivityView(items: markerFiles)
                }
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
                        .lineLimit(1)
                        .fixedSize()
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(Color.purple.opacity(0.6))
                        .clipShape(Capsule())
                }
                Spacer()
                if !model.virtualAntenna {
                    Text(model.referenceQuality.rawValue)
                        .font(.caption2.bold())
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .background(referenceColor.opacity(0.22))
                        .clipShape(Capsule())
                }
                if model.detectionMode == .colorSticker {
                    Text("PASTILLE \(model.stickerColor.rawValue.uppercased())")
                        .font(.caption2.bold())
                        .lineLimit(1)
                        .fixedSize()
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(Color.red.opacity(0.6))
                        .clipShape(Capsule())
                }
                if model.isRecording {
                    Text("● REC \(model.recordedFrames)")
                        .font(.caption2.bold().monospacedDigit())
                        .foregroundStyle(.red)
                        .lineLimit(1)
                        .fixedSize()
                }
                if !topExpanded {
                    Text("\(model.confirmedMicros)/\(model.expectedMicrophones) micros")
                        .font(.caption.monospacedDigit())
                        .lineLimit(1)
                        .fixedSize()
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
                metric("\(model.confirmedMicros)/\(model.expectedMicrophones)", "micros")
                metric("±\(Int(model.planeDeltaCm))", "cm plan")
            }

            HStack(spacing: 6) {
                ForEach(0..<4, id: \.self) { id in
                    // Blue = memorized, orange = in view but not memorized yet, grey = not seen.
                    let mapped = model.mappedMarkerIDs.contains(id)
                    let visible = model.visibleMarkerIDs.contains(id)
                    Text("ID\(id)")
                        .font(.caption2.bold())
                        .foregroundStyle(mapped || visible ? .white : .secondary)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(
                            mapped ? Color.blue.opacity(0.72)
                                : visible ? Color.orange.opacity(0.75)
                                : Color.black.opacity(0.36)
                        )
                        .overlay(Capsule().stroke(visible ? Color.white : .clear, lineWidth: 1.5))
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

                Button {
                    exportMicrophones()
                } label: {
                    Image(systemName: "square.and.arrow.up")
                }
                .buttonStyle(.bordered)
                .disabled(model.numberedMicrophones.isEmpty)

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
        .alert("Nombre de micros différent", isPresented: $confirmIncompleteExport) {
            Button("Exporter quand même") { writeExport() }
            Button("Annuler", role: .cancel) {}
        } message: {
            Text("\(model.numberedMicrophones.count) micros verts pour \(model.expectedMicrophones) attendus : à partir du premier micro manquant ou en trop, les numéros ne correspondront plus aux voies réelles.")
        }
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

            if let grid = model.gridSummary {
                Text(grid)
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.yellow)
                    .lineLimit(2)
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

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) {
                    legend(.green, "dans plan")
                    legend(.orange, "provisoire")
                    legend(.red, "hors plan")
                    legend(.cyan, "orange")
                }
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 10) {
                        legend(.green, "dans plan")
                        legend(.orange, "provisoire")
                    }
                    HStack(spacing: 10) {
                        legend(.red, "hors plan")
                        legend(.cyan, "orange")
                    }
                }
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
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label).font(.caption2).foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.22), in: RoundedRectangle(cornerRadius: 9))
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(text).font(.caption2).lineLimit(1).fixedSize()
        }
    }

    // MARK: - Settings rows

    private func settingLabel(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
            Text(value)
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(.secondary)
        }
    }

    /// Label and value stacked on the left, +/- on the right: long labels wrap instead of truncating.
    private func stepperRow<V: Strideable>(
        _ title: String,
        _ value: String,
        _ binding: Binding<V>,
        _ range: ClosedRange<V>,
        _ step: V.Stride
    ) -> some View {
        Stepper(value: binding, in: range, step: step) {
            settingLabel(title, value)
        }
    }

    // MARK: - Real antenna frame

    private func coordinateField(_ name: String, _ value: Binding<Double>) -> some View {
        HStack(spacing: 3) {
            Text(name).font(.caption.bold())
            TextField(name, value: value, format: .number.precision(.fractionLength(0...4)))
                .keyboardType(.numbersAndPunctuation)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func residualText(channel: Int) -> String {
        guard case .success(let registration) = model.registration,
              let error = registration.residualsMm[channel] else { return "" }
        return String(format: "écart %.1f mm", error)
    }

    private var registrationSummary: String {
        switch model.registration {
        case .success(let registration) where registration.translationOnly:
            return "1 référence : translation seule, les axes de la face sont supposés alignés sur le repère réel. Ajouter au moins 2 autres voies non alignées pour corriger aussi la rotation."
        case .success(let registration):
            let z = registration.transform.rotation * SIMD3<Double>(0, 0, 1)
            return String(
                format: "Recalage sur %d voies : RMS %.1f mm, rotation %.1f°. L'axe Z de la face devient (%.2f ; %.2f ; %.2f) dans le repère réel : il doit pointer vers l'extérieur du cube. Un écart > 10 mm signale une erreur de numérotation ou de scan.",
                registration.residualsMm.count, registration.rmsMm, registration.transform.rotationDegrees, z.x, z.y, z.z
            )
        case .failure(.noReference):
            return "Positions réelles en mètres (même repère que vos fichiers data_geo). Donner au moins 3 voies non alignées, idéalement les 4 coins de la face."
        case .failure(.twoReferences):
            return "2 références ne fixent pas la rotation : ajouter une 3e voie, non alignée avec les deux autres."
        case .failure(.collinear):
            return "Références presque alignées : choisir des voies sur au moins 2 colonnes et 2 hauteurs différentes."
        case .failure(.missingChannels(let channels)):
            return "Voies pas encore scannées (pas de micro vert avec ce numéro) : " + channels.map(String.init).joined(separator: ", ")
        }
    }

    // MARK: - Export

    /// Printable PDF of the four markers at the configured size, shared from the settings sheet.
    private func exportMarkerSheet() {
        let url = AppFolders.documents("Marqueurs")
            .appendingPathComponent(String(format: "CubeMEMS_marqueurs_ArUco_%.0fmm.pdf", model.markerSizeCm * 10))
        do {
            try MarkerSheet.pdf(markerSizeMm: model.markerSizeCm * 10).write(to: url)
            markerFiles = [url]
            showMarkerShare = true
        } catch {
            exportError = error.localizedDescription
        }
    }

    /// Asks for confirmation when the count differs from the expected one, then exports.
    private func exportMicrophones() {
        guard !model.numberedMicrophones.isEmpty else { return }
        if model.numberedMicrophones.count != model.expectedMicrophones {
            confirmIncompleteExport = true
        } else {
            writeExport()
        }
    }

    /// Writes the geometry file (beamforming format) and a detailed file, then opens the share sheet.
    private func writeExport() {
        let microphones = model.numberedMicrophones
        guard !microphones.isEmpty else { return }

        var transform: RigidTransform?
        if model.useRealFrame {
            switch model.registration {
            case .success(let registration):
                transform = registration.transform
            case .failure:
                exportError = "Recalage dans le repère réel impossible : \(registrationSummary)"
                return
            }
        }

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let stamp = formatter.string(from: Date())
        let prefix = model.virtualAntenna ? "CubeMEMS_virtuel" : "CubeMEMS_face"
        let directory = AppFolders.documents("Exports")

        // Raw geometry (face frame) is always exported; the corrected one (real frame) too when registered.
        let rawURL = directory.appendingPathComponent("\(prefix)_\(stamp)_brut_\(microphones.count)mu.csv")
        let realURL = directory.appendingPathComponent("\(prefix)_\(stamp)_reel_\(microphones.count)mu.csv")
        let detailsURL = directory.appendingPathComponent("\(prefix)_\(stamp)_details.csv")

        do {
            var files: [URL] = []
            let slots = model.useGridNumbering && !model.virtualAntenna ? model.gridLayout.count : nil
            try MicrophoneExport.geometryCSV(microphones, slotCount: slots)
                .write(to: rawURL, atomically: true, encoding: .utf8)
            files.append(rawURL)
            if let transform {
                try MicrophoneExport.geometryCSV(microphones, transform: transform, slotCount: slots)
                    .write(to: realURL, atomically: true, encoding: .utf8)
                files.append(realURL)
            }
            try MicrophoneExport.detailedCSV(microphones, transform: transform)
                .write(to: detailsURL, atomically: true, encoding: .utf8)
            files.append(detailsURL)
            exportFiles = files
            showExport = true
        } catch {
            exportError = error.localizedDescription
        }
    }
}

/// UIKit share sheet: save to Files, AirDrop, mail…
private struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
