# Cube MEMS — calibration géométrique

Cette branche regroupe les deux prototypes de calibration géométrique de l'antenne Cube MEMS :

- **application iPhone native ARKit** : `ios/CubeMEMSARKit/`
- **version web de démonstration** : `web/`

## Application native ARKit

Projet Xcode :

`ios/CubeMEMSARKit/CubeMEMSARKit.xcodeproj`

Principaux fichiers :
- `ARScannerView.swift` : session ARKit, repère face, triangulation, filtrage et recalage.
- `ArucoReferenceFactory.swift` : références ArUco ID 0–3.
- `CapsuleDetector.swift` : détection visuelle des capsules.
- `ScanModel.swift` : état et paramètres du scan.
- `ContentView.swift` : interface utilisateur.

## Version web

Dossier :

`web/`

La version web correspond au prototype **Cube MEMS — scan V2** et contient :
- `index.html`
- `app-v2.js`
- `aruco-lite.js`
- `style.css`

Elle sert de prototype navigateur et de banc de test des algorithmes 2D. La version de référence pour le suivi 6-DoF et la reconstruction 3D reste l'application native ARKit.

## Branche

Cette branche est volontairement séparée des outils de beamforming, acquisition et traitement acoustique du dépôt.
