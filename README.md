# Cube MEMS — application de calibration géométrique

Cette branche contient uniquement l'application iPhone native ARKit utilisée pour reconstruire la position 3D des capsules/microphones de l'antenne Cube MEMS.

## Application

Le projet Xcode est dans :

`ios/CubeMEMSARKit/`

Principaux fichiers :
- `ARScannerView.swift` : session ARKit, repère face, triangulation, filtrage et recalage.
- `ArucoReferenceFactory.swift` : références ArUco ID 0–3.
- `CapsuleDetector.swift` : détection visuelle des capsules.
- `ScanModel.swift` : état et paramètres du scan.
- `ContentView.swift` : interface utilisateur.

## Branche

Cette branche est volontairement séparée du code de beamforming, de l'ancienne démo web et des autres outils du dépôt.

Version de départ : V3 ARKit.
