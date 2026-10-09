# CLAUDE.md — Cube MEMS, calibration géométrique par iPhone / ARKit

## Objectif

App iPhone native (ARKit) qui reconstruit la position 3D des ~240 capsules MEMS d'une antenne acoustique cubique (~2 m × 2 m × 2 m, structure noire, faces en grillage, capsules = petites pastilles blanches). Le scan se fait en marchant autour de l'antenne, en chambre anéchoïque (beaucoup d'objets blancs en arrière-plan → nombreux faux positifs 2D).

Sortie visée par micro : identifiant, X/Y/Z dans un repère lié au cube, incertitude, export CSV/JSON.

**96 micros par face** (réglage `expectedMicrophonesPerFace`). Numérotation des voies, vue de face devant la grille : n° 1 = en bas à droite, on remonte la colonne de droite, puis la colonne suivante vers la gauche de bas en haut, etc. (`Core/MicrophoneExport.swift`). Export : `…_<N>mu.csv` au format `data_geo` des outils de beamforming (`X;Y;Z`, m, `;`, une ligne par voie, repère de la face : origine centre des 4 ArUco, X droite, Y haut, Z vers l'opérateur) + `…_details.csv`. Numéros affichés en AR à côté des micros verts ; avertissement à l'export si le compte ≠ attendu.

Repère de la face (`lockFaceIfReady`) : origine = barycentre des 4 centres ArUco (z = 0 sur la surface des marqueurs), X = milieu[ID0,ID3] → milieu[ID1,ID2], Y ⟂ X vers le haut, Z = X × Y vers l'opérateur ; gravité non utilisée. `planeOffsetCm` est compté sur Z (positif = capsules devant les marqueurs, côté opérateur ; **signe à vérifier sur l'antenne**). Axes X/Y/Z affichés en AR (réglage `showFaceAxes`). Passage au repère réel de l'antenne : dans l'app (Réglages › Repère réel : voies de référence + positions réelles en m, mémorisées ; `Core/RigidRegistration.swift`, méthode de Horn, ≥ 3 voies non alignées, 1 voie = translation seule ; export `_reel`) ou hors app avec `tools/recalage/recaler_repere.py` (même calcul, Kabsch).

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

## Recalage ArUco et dérive (V4)

- `Core/FaceRecalibration.swift` : logique de `softRecalibrate` (inchangée), partagée app + simulateur.
- Les rayons sont stockés **dans le repère de la face** au moment de l'observation (`MicroTrack.rays`, `localPoint`) ; un recalage ne fait que déplacer la face (`faceDidMove`). Pour une dérive en translation pure c'est équivalent à l'ancienne correction rétroactive, mais correct aussi en rotation.
- Dérive simulée 1 cm/m avec ArUco aux coins (120 s) : sans limite RMS 13 mm / 11 imprécis ; limite 3 m → 10,6 mm ; **limite 1,5 m → 6,6 mm, 98 %, 0 faux** (défaut `maxTravelSinceRecalM` = 1,5 m : au-delà, plus de nouveaux rayons jusqu'au prochain ArUco). Sans ArUco du tout : 36 % / 43 faux (seul `knownIssue` restant).
- La dérive réelle d'ARKit est probablement plus faible que 1 cm/m : la limite pourra être relevée après mesure sur l'antenne.

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

## Capsules réelles et détection (7/10/2026)

Capsules = disques blancs d'**environ 20 mm** clipsés sur des câbles verticaux noirs (colonnes), devant un filet souple qui ondule ; on voit à travers le cube les capsules des autres faces et le fond de dièdres blancs, souvent plus clairs que les capsules à l'ombre. iPhone **sans LiDAR**. Le détecteur actuel (seuil de luminance absolu) rate les capsules à l'ombre et prend des centaines de morceaux de fond (portage Python testé sur photos) ; à distance de scan, maille et capsule ont la même taille à l'écran → la discrimination repose sur la 3D. Défauts passés à diamètre 20 mm et plan ±5 cm.

Mode **enregistrement** (Réglages › Enregistrement, `ScanRecorder.swift`) : 1 image JPEG / 0,5 s + `frames.jsonl` (pose caméra, intrinsèques, suivi, ArUco vus, face) + `meta.json` (réglages), zip partagé. Rejeu sur PC : `tools/replay/rejouer_enregistrement.py` (projection face/ArUco + détecteur app porté). Prochaine étape : régler le détecteur (contraste local, forme) sur un vrai enregistrement.

## Premier scan réel (8/10/2026, rejeu PC)

- **ARKit ne reconnaît pas les ArUco imprimés** (0 détection sur 65 images) alors qu'OpenCV les lit à 35–120 px → détecteur ArUco maison `Core/ArucoDetector.swift` (référence Python `tools/replay/aruco_detector.py`, fixtures réelles dans les tests) : 37/37 + 4 ID3 sur papier gondolé, centre ±1,3 px. Centres triangulés multi-vues (≥ 3 vues, ≥ 15 cm de déplacement, résidu ≤ 3 cm), recalage par décalage perpendiculaire rayon/centre. Convention caméra validée (distances entre marqueurs cohérentes, face 1,95 × 1,83 m).
- **Le filet n'est pas plan** : capsules 4 à 14 cm **derrière** les ArUco (ventre vers l'intérieur au centre de la face). Défauts passés à plan −8 cm ± 10 cm (sans risque pour les autres faces, à ≥ 1 m).
- Capsules vues par le détecteur blanc ≈ **27 mm** (pas de grille 4 px) → défaut 27 mm.
- Rejeu complet (`tools/replay/rejouer_complet.py`, mode `all`) : **35 micros verts, tous sur des capsules de la face scannée**, aucun faux vert ; scan de 32 s couvrant surtout la moitié basse → refaire un scan plus long couvrant toute la face, en filmant les 4 ArUco.

## Numérotation par grille (option « Grille régulière », activée par défaut)

`Core/GridNumbering.swift` (référence `tools/replay/grille.py`) : micros groupés en colonnes/rangs par les écarts entre eux (écartements inégaux et colonnes pas droites acceptés), 12 colonnes → placement direct ; scan partiel → placement des groupes observés dans les 12 cases au plus proche d'un pas uniforme (signalé « numéros provisoires » si ambigu) ; chaque colonne/rang recentré sur la médiane de ses micros ; un micro prend le numéro de sa case (trou au lieu de décalage). Export `_brut`/`_reel` : 96 lignes, `nan;nan;nan` pour les cases vides. Affichage « Grille 12×8 : N/96 cases — manquent … ». Les positions exportées restent les positions mesurées.

## Suite prévue : multi-face (en attente de l'essai réel sur une face, 7/10/2026)

Antenne : **5 faces × 96 micros = 480 voies**, colonnes de 8 (coins d'une face : 1, 8, 89, 96). Approche retenue : **scan face par face**, chaque face avec ses 4 ArUco (même jeu déplacé) et son recalage par ses 4 coins dans le repère réel commun ; sélecteur de face dans l'app, décalage de voies (face k → 96(k−1)+1 … 96k), références mémorisées par face, accumulation des faces validées et export fusionné de 480 lignes au format `data_geo` (+ fichiers par face bruts/corrigés). Questions ouvertes pour l'utilisateur : ordre des faces dans les voies, sens « haut » de chaque face (surtout le dessus), source des positions réelles des coins (CAO / GEO nominal ou mesure).

Face du dessus : impossible de se placer derrière les micros (au-dessus) → scan **par en dessous, depuis l'intérieur** ; ArUco collés sous les tubes, ordre ID0…ID3 défini vu d'en dessous ; distance faible (~0,5–1 m, tenir le téléphone bas) ; numérotation **miroir** à prévoir (option par face « vue de l'intérieur ») — en attente de la convention de numérotation de cette face. Idée validée à tester : **gommettes de couleur** (rose fluo ou bleu, 10–12 mm, centrées, sans masquer l'évent du MEMS, éventuellement alternées par colonne) pour une détection par couleur qui ignore le fond et les autres faces.

Avant cela, l'essai réel sur une face doit valider : détection réelle, une seule vue caméra, sens de Z et signe de `planeOffsetCm`, numérotation, RMS du recalage par les coins.

## Architecture cible

- Stocker observations et points **dans le repère local du cube** (`rayon monde → monde→cube`), et ne passer au monde ARKit que pour l'affichage. Aujourd'hui, le recalage corrige rétroactivement les rayons/points en repère monde : acceptable pour le prototype, pas propre à terme.
- La profondeur 3D (triangulation + distance au plan) doit rester le principal discriminant contre les capsules d'autres faces visibles à travers le grillage et contre les objets blancs de la chambre.

## Conventions

- Identifiants et commentaires en anglais, textes d'interface en français ; échanges avec l'utilisateur en français.
- Les paramètres réglables vivent dans `ScanModel.swift` et sont exposés dans `ContentView.swift` ; garder cette séparation pour tout nouveau seuil.
- Un micro vert doit toujours pouvoir être invalidé par des observations ultérieures.
