# Cube MEMS — iOS ARKit V3

Prototype natif iPhone pour cartographier une face de l’antenne MEMS.

## Objectif de cette V3

- ARKit suit la pose 6-DoF de l’iPhone en continu.
- Les ArUco 4x4_50 ID 0, 1, 2, 3 sont utilisés comme **images de référence ARKit**.
- Les quatre marqueurs **n’ont pas besoin d’être visibles simultanément**.
- Dès qu’un marqueur est vu, sa position 3D est mémorisée dans le repère monde ARKit.
- Quand les quatre IDs ont été vus au moins une fois, le rectangle de la face est verrouillé dans l’espace et reste affiché même si les ArUco quittent le champ.
- Les capsules blanches sont détectées dans le flux caméra.
- Chaque détection produit un rayon caméra. Plusieurs rayons servent à trianguler la capsule en 3D.
- Un micro est validé si sa position 3D est dans le plan de la face avec une tolérance réglable ±Δ.
- Mode de centre : centroïde blanc, centre contour, ou comparaison des deux.

## Hypothèses du premier test

- carré noir ArUco imprimé : 80 mm ;
- ID 0 = haut-gauche ;
- ID 1 = haut-droite ;
- ID 2 = bas-droite ;
- ID 3 = bas-gauche ;
- les quatre marqueurs sont à peu près dans le même plan ;
- le plan des capsules peut être décalé de quelques cm par rapport au plan des ArUco.

La V3 utilise directement les positions ARKit réellement observées des quatre marqueurs : ils peuvent donc être acquis successivement.

## Ouvrir le projet

Le dossier contient un fichier `project.yml` pour XcodeGen.

Sur un Mac :

```bash
brew install xcodegen
cd ios/CubeMEMSARKit
xcodegen generate
open CubeMEMSARKit.xcodeproj
```

Dans Xcode :
1. sélectionner son équipe de signature dans Signing & Capabilities ;
2. brancher l’iPhone ;
3. lancer l’app sur l’iPhone réel (ARKit ne se teste pas correctement dans le simulateur) ;
4. autoriser la caméra.

## Procédure de test

1. Démarrer le scan.
2. Montrer ID0, puis se déplacer.
3. Montrer ID1, ID2 et ID3 quand ils entrent dans le champ.
4. Les pastilles de coins deviennent mémorisées une par une.
5. Quand les quatre sont acquises, le rectangle vert passe en état verrouillé.
6. Se déplacer latéralement devant la face : les capsules deviennent provisoires puis validées si leur triangulation reste dans le plan ±Δ.

## Vidéo de test

Une vidéo iPhone exportée est utile pour régler les seuils de détection, la taille apparente des capsules et les cas d’occlusion. Elle ne contient cependant pas la trajectoire ARKit 6-DoF d’une session native ; pour valider la métrologie 3D, le test final doit être fait dans l’app ARKit elle-même.
