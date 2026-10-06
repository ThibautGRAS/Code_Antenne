# CLAUDE.md — Cube MEMS, calibration géométrique par iPhone / ARKit

## Objectif

App iPhone native (ARKit) qui reconstruit la position 3D des ~240 capsules MEMS d'une antenne acoustique cubique (~2 m × 2 m × 2 m, structure noire, faces en grillage, capsules = petites pastilles blanches). Le scan se fait en marchant autour de l'antenne, en chambre anéchoïque (beaucoup d'objets blancs en arrière-plan → nombreux faux positifs 2D).

Sortie visée par micro : identifiant, X/Y/Z dans un repère lié au cube, incertitude, export CSV/JSON.

## Dépôt et branches

- Dépôt : `ThibautGRAS/Code_Antenne`, branche de travail **`calibration-app`** (créée au commit `923e95e`). Contenu : `README.md`, `.gitignore`, `ios/CubeMEMSARKit/` (app native, **référence**) et `web/` (prototype navigateur « Cube MEMS — scan V2 » : `index.html`, `app-v2.js`, `aruco-lite.js`, `style.css`).
- `web/` sert de banc de test des algorithmes 2D (pose depuis ArUco + FOV approximatif). Ce n'est pas la référence pour la 6-DoF ni la reconstruction 3D.
- `gh-pages` : branche historique (beamforming Python, acquisition, ancienne démo web à la racine). Ne pas la modifier depuis ce travail.
- Une app ARKit ne se déploie pas sur GitHub Pages (Safari/AR Quick Look ne donne pas accès aux frames ni à la pose 6-DoF). Distribution future envisagée : GitHub Actions → build Xcode → TestFlight.

## Build et test

- Projet : `ios/CubeMEMSARKit/CubeMEMSARKit.xcodeproj` (généré depuis `project.yml`, XcodeGen).
- Nécessite macOS + Xcode + **iPhone réel** (ARKit n'est pas validable dans le simulateur). Choisir une équipe de signature, lancer, autoriser la caméra.
- La machine de dev actuelle est sous Windows : impossible de compiler ici. Relire attentivement le Swift modifié (types `simd`, optionnels, threads) et le signaler à l'utilisateur.
- CI (`.github/workflows/ios-ipa.yml`, push sur `calibration-app` touchant `ios/**`) : job `core-tests` (`swift test` du package `ios/CubeMEMSARKit/Package.swift`) + job `build` (XcodeGen → `.ipa` non signé, publié dans la release publique `ipa-latest`). Les résumés de scénarios et les échecs sont lisibles sans authentification via l'API `check-runs/{job_id}/annotations`.
- Installer sur iPhone depuis Windows : télécharger `https://github.com/ThibautGRAS/Code_Antenne/releases/download/ipa-latest/CubeMEMSARKit-unsigned.ipa` à la racine du dépôt local (ignoré par git), puis Sideloadly (Apple ID gratuit, 7 jours). Le pilote USB Apple x64 (538.0.0.0) a été installé manuellement sur ce PC.
- Tout fichier Swift ajouté à l'app doit aussi être ajouté à la main dans `CubeMEMSARKit.xcodeproj/project.pbxproj` (projet écrit à la main, IDs `A1…`/`B1…`), en plus de `project.yml`.
- La vidéo `IMG_5904.mp4` permet de tester détection ArUco/capsules, seuils et flou, mais pas la reconstruction 3D (pas de trajectoire ARKit).

## Code (`ios/CubeMEMSARKit/CubeMEMSARKit/`)

| Fichier | Rôle |
|---|---|
| `ARScannerView.swift` | `ARView` + coordinator : session ARKit, acquisition ArUco, `faceTransform`, rayons, association, triangulation, filtres, recalage (`softRecalibrate(using:)`), indicateur de dérive, filtre mouvement |
| `CapsuleDetector.swift` | Détection sur le `CVPixelBuffer` YCbCr : seuil luminance + chroma neutre, composantes connexes, filtres diamètre/aspect/remplissage ; détection orange de référence |
| `ArucoReferenceFactory.swift` | Références ArUco ID 0–3 |
| `ScanModel.swift` | État et paramètres réglables (`@Published`) |
| `ContentView.swift` | UI SwiftUI, steppers de paramètres, métriques |
| `Core/ReconstructionCore.swift` | **Sans ARKit** : `FaceGeometry` (intersection plan), `CapsuleSizeFilter`, `Triangulation`, `ReconstructionParameters`, `TrackReconstructor` (association, validation, recalage rigide). Utilisé par l'app et les tests |
| `Core/VirtualAntenna.swift` | **Sans ARKit** : antenne virtuelle (capsules, face arrière, objets blancs), détections synthétiques d'une caméra pinhole, `ReconstructionScorer` (doublons, faux verts, RMS vs vérité terrain) |

Hors app :
- `ios/CubeMEMSARKit/Package.swift` + `Tests/CubeMEMSCoreTests/` : tests géométriques + scénarios de scan simulés (`ScanSimulator`). Les scénarios qui échouent encore sont marqués `knownIssue` (XCTExpectFailure strict) : quand un correctif les fait passer, la CI devient rouge → retirer le marqueur.
- `tools/simulateur-3d/index.html` : simulateur 3D local (double-clic, Three.js via CDN) avec curseurs de réglage. Copie **JavaScript** de la logique du cœur Swift : toute modification de `ReconstructionCore.swift` doit y être reportée.
- Mode « Antenne virtuelle » dans l'app (Réglages › Test sans antenne) : face virtuelle posée à 1,6 m, détections synthétiques depuis la vraie pose ARKit, score vérité terrain affiché en direct.

## Principe de reconstruction (V3 ARKit, non validée métrologiquement)

1. 4 ArUco `DICT_4X4_50`, 80 mm, sur une face : ID0 haut-gauche, ID1 haut-droite, ID2 bas-droite, ID3 bas-gauche.
2. Acquisition **progressive** : les 4 marqueurs n'ont pas besoin d'être visibles ensemble (ils le sont rarement). Positions mémorisées dans `markerCenters`, `markerTransforms`, `markerLocalTransforms` jusqu'au reset.
3. Les 4 acquis → `faceTransform` construit, face verrouillée. Plan des capsules décalé de `planeOffsetCm` (3 cm, **provisoire**, à mesurer).
4. ARKit suit seul ensuite. Un ArUco revu ne sert plus qu'au recalage : `pose face ≈ pose monde ArUco × inverse(pose locale)`, lissage 0.12 / 0.24 / 0.38 (1 / 2 / ≥3 marqueurs), rejet si saut > 35 cm ou > 20°.
5. Indicateur de dérive (distance parcourue depuis le dernier recalage) : < 2,5 m `REPÈRE OK`, < 4 m `À RECALER`, sinon `RECALAGE CONSEILLÉ`.
6. Détection capsule → centre (centroïde blanc, centre contour, ou comparaison `+`/`×` ; le « centre contour » est une estimation PCA, pas un vrai fit d'ellipse).
7. Filtre de taille physique : `d_px ≈ f_px × d_m / profondeur_m`, avec `capsuleDiameterMm` = 30 mm (**provisoire**) et `capsuleSizeTolerancePct` = ±60 %.
8. Chaque détection → rayon monde (origine caméra, direction pixel) stocké dans un `MicroTrack`. Association par position projetée dans le plan de la face (`associationCm` = 10 cm).
9. Triangulation moindres carrés non pondérée : `A = Σ(I − d dᵀ)`, `b = Σ(I − d dᵀ)o`, `x = A⁻¹b`, + résidu moyen perpendiculaire.
10. Vert si ≥ 4 rayons, baseline ≥ `minBaselineCm` (20 cm), distance au plan ≤ `planeDeltaCm` (±8 cm), résidu sous la limite.
11. États : orange = provisoire, vert = confirmé, rouge = rejeté.
12. Filtre mouvement : pas de nouveau rayon si translation > 1,2 m/s ou rotation > 1,6 rad/s (le repère et les micros restent affichés).

## V4 (6/10/2026) — association, validation, incertitude

- Les tracks **confirmés** sont associés sur la position XY de leur point triangulé, sans limite de temps (plus de doublon quand une capsule ressort du champ) ; les autres sur la dernière intersection plan, avec `associationMaxFrameGap`.
- Deux verts à moins de `mergeRadius` (2 cm) sont fusionnés.
- `Triangulation.robustTriangulate` : solution non pondérée, puis 2 tours de rejet des rayons > max(1 cm, 3 × médiane) et moindres carrés pondérés 1/σᵢ² (σᵢ = 1,5 mrad × distance) ; **incertitude = √trace(Cov)**. Test de dégénérescence normalisé (`det > 1e-5·W³`).
- Vert si : ≥ 7 rayons, baseline ≥ 30 cm, incertitude ≤ 8 mm, |plan| ≤ 3 cm, résidu ≤ 2 cm. Rouge si |plan| > 1,5 × tolérance + 2σ. Un vert redevient orange s'il devient incohérent (réévalué à chaque image).
- Réglages par défaut (`ScanModel`) : association 4,5 cm, 7 rayons, baseline 30 cm, plan ±3 cm, taille ±30 %, incertitude 8 mm.
- Simulateur JS : 42/42 capsules, 0 doublon, 0 faux vert, RMS < 2 mm dans tous les scénarios sauf dérive sans ArUco (connu, à traiter par le recalage).
- Mode virtuel : les capsules virtuelles sont fixes dans le repère ARKit, donc la dérive ARKit n'y a **aucun** effet (pas d'ArUco ni d'indicateur de recalage dans ce mode). Le 1er essai virtuel V3 (RMS 10 mm, 9 doublons, 6 faux) était dû à la faible parallaxe, pas à la dérive.

## Résultats de la simulation V3 (réglages du 1er essai, 6/10/2026)

Sur 42 capsules : ~220 micros verts même en salle vide (**~180 doublons**, cause principale de « l'accumulation » : une capsule hors champ > `associationMaxFrameGap` = 40 images ≈ 0,7 s n'est plus associable → nouveau track → nouveau vert). En chambre anéchoïque : ~135–150 faux verts en plus ; les seuils durcis (assoc 4,5 cm, 7 rayons, baseline 30 cm, plan ±3 cm, taille ±30 %) les ramènent à 0 mais pas les doublons. Dérive 1 cm/m sans recalage : recall 62 %, ~120 faux verts. Triangulation : le seuil de déterminant 1e-7 laisse passer des rayons parallèles.

## Problèmes connus (premier essai réel)

1. **Deux vues caméra visibles** alors que le code ne crée qu'un `ARView`. Pistes : ancienne build installée, mauvais target, duplication dans le projet généré, double instanciation SwiftUI. Non résolu.
2. **ArUco qui semblent oubliés** : la mémoire existe dans le code, c'est surtout l'UI. Il faut afficher distinctement `VISIBLE` et `MÉMORISÉ` par ID.
3. **Faux micros verts qui s'accumulent** (problème principal). Causes : association trop large, trop peu de rayons, baseline faible, pas de critère d'angle de parallaxe, tolérance plan et taille trop larges, triangulation non robuste, aucun moyen de rétrograder un vert.

## Priorités (une seule face d'abord, pas de fonctionnalités secondaires)

1. Résoudre les deux vues caméra.
2. Rendre l'état `MÉMORISÉ` des ArUco évident.
3. Empêcher les faux verts et durcir la validation. Valeurs de départ à tester : association 4–5 cm, ≥ 6–8 rayons, baseline ≈ 30 cm, plan ±3 cm, taille ±30 %.
4. Ajouter un angle de parallaxe minimal entre rayons (quelques degrés, à valider).
5. Triangulation robuste : pondération `A = Σ wᵢ(I − dᵢdᵢᵀ)` (segmentation, netteté, accord centroïde/contour, taille, parallaxe, état tracking ARKit) + Huber/Tukey ou RANSAC / rejet itératif, puis covariance ou indicateur d'incertitude.
6. Vieillissement des tracks, score de confiance, rétrogradation vert → orange et suppression des tracks incohérents.
7. Nouvel essai iPhone, puis comparaison des XYZ à des positions de référence (repères orange sur capsules connues).
8. Seulement ensuite : export CSV/JSON finalisé, multi-face (repère cube global + transformation par face).

## Architecture cible

- Stocker observations et points **dans le repère local du cube** (`rayon monde → monde→cube`), et ne passer au monde ARKit que pour l'affichage. Aujourd'hui, le recalage corrige rétroactivement les rayons/points en repère monde : acceptable pour le prototype, pas propre à terme.
- La profondeur 3D (triangulation + distance au plan) doit rester le principal discriminant contre les capsules d'autres faces visibles à travers le grillage et contre les objets blancs de la chambre.

## Conventions

- Identifiants et commentaires en anglais, textes d'interface en français ; échanges avec l'utilisateur en français.
- Les paramètres réglables vivent dans `ScanModel.swift` et sont exposés dans `ContentView.swift` ; garder cette séparation pour tout nouveau seuil.
- Un micro vert doit toujours pouvoir être invalidé par des observations ultérieures.
