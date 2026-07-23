# Journal de travail — AntenneMu

> But : tracer les modifications (notamment celles faites avec Claude Code) pour
> reprendre le contexte rapidement. Ordre antéchronologique (le plus récent en haut).
> Convention : on note **quoi**, **pourquoi**, et le **hash de commit** quand il existe.

---

## Conventions (philosophie du code)
Code de recherche : on privilégie la **lisibilité** à l'abstraction.
1. **Main lisible de haut en bas** : params en tête (Python, `Config(overrides=...)`),
   puis le flux visible (charger → calculer → visualiser).
2. **Réutiliser le lourd via des fonctions simples** + objet de résultats explicite :
   `compute_xxx(config) -> res` une fois, puis `plot_a(res)`, `plot_b(res)`.
3. **Noyau pur partagé** (`signal_process`, `beamforming`) : pas d'I/O, pas d'UI,
   pas de god-config qui fuit dedans.
4. **Règle de trois** : n'abstraire (classe, couche, framework) qu'au 3ᵉ besoin réel.
   `src/pipelines/` est laissé **dormant** — ni étendu, ni supprimé (framework pour 1 seul usage).

---

## Prochaine étape (à reprendre plus tard)
**Retrait de l'UI OpenCV** — objectif : supprimer `src/live/ui.py` (dernier reste du legacy OpenCV).

- **Blocage actuel :** `src/live/ui_qt.py` importe `src/live/display.py` (pour `SHORTCUTS` et
  `process_keyboard_from_key`), et `display.py` fait `from src.live.ui import (handle_key,
  draw_header_bar, …)`. Donc `ui_qt` dépend **transitivement** de `ui.py`.
- **À faire :**
  1. Repérer ce que `ui_qt` utilise réellement : `SHORTCUTS` (liste) + `process_keyboard_from_key`
     (qui s'appuie sur `handle_key` de `ui.py`).
  2. Reloger ça dans un module **sans dépendance OpenCV** (la logique clavier + la liste des
     raccourcis, p. ex. dans `ui_qt` ou un petit `live/shortcuts.py`).
  3. Couper le `from src.live.ui import …` de `display.py` (ou sortir `display.py` du chemin Qt
     s'il ne sert plus qu'à l'OpenCV).
  4. Vérifier que `ui_qt` importe et tourne, **puis supprimer `ui.py`**.
- **Prudence :** ça touche l'appli live → faire un **plan détaillé d'abord**, et tester
  l'import de `ui_qt` après chaque étape.

---

## 2026-06-28

### App/visu — fond STL gris derrière la carte + rail d'icônes + version compacte
- **Fond derrière la carte** : mode STL → **STL gris légèrement en retrait (0.97)** (non coïncident,
  sinon il masque le fondu) ; mode OBJ → l'objet texturé. La transparence de la carte révèle donc
  **l'objet** (plus le vide). Vérifié par rendu (fondu + STL gris derrière).
- **Navigation en rail d'ICÔNES** (sidebar 66 px) : icône + info-bulle du nom complet ; le bandeau
  affiche la page courante. → gros gain de place pour le contenu.
- **Version « v1.0.0 »** en bas du rail. Échelle **OBJ / BF** grisée sans OBJ (a du sens seulement
  avec un OBJ : aligner l'objet scanné fin sur le maillage BF refait).

### visu — FONDU restauré et VÉRIFIÉ (RGBA par point) + pas de base grise coïncidente en STL
- **Cause du « toujours gris »** (vérifiée par rendus hors-écran) : (1) passer l'opacité en **tableau**
  au param `opacity` **casse le coloriage** dans pyvista (iso11/iso15 gris) ; (2) un overlay
  translucide est **masqué par une base opaque coïncidente** (iso8/9/10/13).
- **Fix VÉRIFIÉ** : fondu via **couleurs RGBA par point** (couleur = `cmap(niveau)`, alpha =
  `niveau·map_opacity`, 0 sous la dynamique) → dégradé lisse qui s'estompe. Colorbar conservée via
  un mesh scalaire invisible (opacity 0).
- **Mode STL** : plus de base grise coïncidente (elle masquait le fondu) → le fondu s'affiche seul
  (iso12/bf_render3 : dôme dégradé). **Mode OBJ** : objet texturé séparé + fondu par-dessus
  (iso14 : rendu ASPI). Les deux **confirmés par capture**.

### App/visu — fondu restauré, sélecteur OBJ, échelle OBJ/BF grisée, toggle accordéon, version
- **Rendu : FONDU restauré** (opacité ∝ niveau, 0 sous la dynamique) = le rendu des versions
  précédentes. (Mon « gris » en test venait de l'**OpenGL logiciel headless** — la translucidité
  par-point y est mal rendue ; sur **GPU réel** le fondu marche, comme dans l'ancien code.)
- **Sélecteur « .obj (option) » sous le Mesh STL** : si présent → objet **texturé** (mode OBJ,
  `scanned_mesh`) au lieu du STL gris ; vide → STL gris.
- **Slider « Echelle OBJ / BF »** : **grisé** si pas d'OBJ (ne sert qu'à aligner l'OBJ scanné sur la
  grille BF).
- **Accordéon** : clic sur une carte ouverte la **replie** (bascule).
- **Version** « Cubeam 3D · v1.0.0 » en bas à gauche de la sidebar (`APP_VERSION`).

### App/visu — échelle défaut 1.0, accordéon état fiable, carte opaque par défaut (net)
- **Échelle mesh défaut 1.0** (slider).
- **CollapsibleCard** : état via booléen interne `_expanded` (fiable ; `isVisible` était faussé
  quand la fenêtre n'est pas montrée). Clic = ouvre la carte et la garde ouverte (jamais tout replié).
- **Transparence défaut 0 % (opaque)** : le « moche » venait du **halo de translucidité** — VTK ne
  rend pas correctement l'opacité **par point** par-dessus un objet opaque dans ce contexte
  (diagnostiqué par rendus hors-écran : iso3/5/8/9/10 gris ; iso4/6/7 opaque/scalaire = nets).
  Défaut opaque = **net** (carte colorée + objet sous la dynamique). Slider gardé pour voir à travers.

### visu — FIX rendu : carte enfin visible (cause trouvée par rendu hors-écran)
- **Diagnostic** : j'ai découvert que **pyvista rend en hors-écran** ici (`PYVISTA_OFF_SCREEN`,
  `Plotter(off_screen=True).screenshot`) → j'ai pu tester le rendu moi-même. Isolé le bug :
  passer l'opacité en **TABLEAU** rend le mesh *translucide* → **masqué par le mesh de base opaque**
  → objet tout gris.
- **Fix** : on **DÉCOUPE** la zone dans la dynamique (`threshold` SPL ≥ max−dyn) et on la rend en
  **opacité scalaire** (slider Transparence). Hors dynamique : non dessiné → l'objet gris apparaît.
- **Vérifié par rendu hors-écran** : pic rouge net + dégradé turbo dans la dynamique, objet gris
  au-dessous. C'était la vraie cause du « toujours gris ».

### visu — carte visible : DANS la dynamique = opaque (correctif clé)
- **Bug de visibilité** : l'intérieur de la dynamique était rendu à l'opacité du slider (ex. 40 %)
  → sur une carte piquée + petite dynamique + halo, quasi rien de visible (objet gris).
- **Corrigé** : `opacity = 1.0` **dans** la dynamique (couleurs nettes, toujours visibles) ;
  **hors** dynamique `= map_opacity` (slider ; à 100 % de transparence → 0 → objet visible).
- **Halo** plus petit (`0.006·diag`) pour ne pas masquer le pic ; **dynamique par défaut 15 dB**.
- Label slider → « Transparence (zones hors dynamique) ».

### App + visu — GEO déplacé en étape ②, défauts transparence/dynamique
- **Sélecteur GEO déplacé de l'étape ① → étape ②** (Beamforming) : les positions sont un input du
  **beamforming**, pas de la CSM → **changer le GEO ne recalcule plus la longue CSM**.
  `beamforming_run` charge le GEO depuis le config courant (repli sur `csm.npz`).
- **Défauts** : transparence carte **60 %** (opacité 0.4 dans la dynamique), slider Dynamique borné
  **1–20 dB** (défaut 10). Objectif : la carte reste visible par défaut (objet visible sous la dynamique).
- **Vérifié** : compile, GEO dans `form_bf_main`, défauts sliders, Config OK.

### App + visu — sélecteur GEO (positions micros) + transparence sous-dynamique + slider Dynamique
- **Étape ①** : sélecteur **« Positions micros (GEO) »** (type file, défaut `GEO_256_revised3.csv`
  dans `data/data_geo`) → surcharge `geo_name` (Config recalcule `geo_file`). Changer le GEO
  invalide la CSM (recompute) — cohérent (les positions changent).
- **Transparence** : tout ce qui est **sous la dynamique** (`SPL < SPL_max - dyn`) est **totalement
  transparent** (opacité 0) ; au-dessus = slider *Transparence*. (`beamforming_visu`, autorisé)
- Nouveau **slider « Dynamique (dB) »** dans la carte Affichage (3-40, défaut 10) → `cfg.dyn`,
  re-rendu live (affichage seul, pas de recalcul).
- **Vérifié** : compile, `get_project` (geo_name/dyn/factor) accepté par Config, sélecteur GEO visible.

### App — logo CETIM retiré, Cubeam agrandi
- **Logo CETIM + en-tête de sidebar retirés** → sidebar = **navigation seule** (largeur 210).
- **Logo Cubeam agrandi** (64 px), toujours thème-aware (blanc en sombre / couleur en clair),
  sans plaque, en haut à droite.

### App — logo Cubeam thème-aware (blanc en sombre, sans plaque)
- **Cubeam SVG recoloré à la volée** : navy `#071D45` → **blanc** en thème sombre (accents bleu/rouge
  conservés), couleur en clair. Affiché **sans plaque** ; mis à jour au changement de thème
  (`_refresh_cubeam` appelé par `apply_theme`).
- **CETIM** (PNG couleur) reste sur **plaque blanche** (option B : pas de variante blanche fournie).
- **Vérifié** (captures 2 thèmes) : Cubeam net et intégré, plus de boîte blanche à droite.

### App — logos agrandis + plaque arrondie (dark à finaliser)
- CETIM + Cubeam **agrandis** (sidebar 228, en-têtes 86 px ; CETIM 178w, Cubeam 52h), **plaque
  blanche arrondie** (8 px) + padding. OK en thème clair.
- En **sombre**, la plaque blanche fait « boîte » : pour un rendu sans plaque il faut des
  **variantes claires (blanc)** des logos (à fournir) → thème-aware à brancher ensuite.

### App — logo Cubeam 3D (SVG) branché en haut à droite
- Chargement adapté aux fichiers réels déposés : **SVG prioritaire** (`Cubeam3D_logo_corrige_v2.svg`)
  **rendu net** via `QSvgRenderer` à la hauteur voulue, repli PNG (`logo.png`). Affiché à droite du
  bandeau sur plaque blanche (`Logo2`) → équilibre le logo CETIM à gauche. Vérifié (capture).

### App — logo produit « Cubeam 3D » en haut à droite
- Chargé depuis `app/assets/cubeam3d.png` (fallback `data/assets/cubeam3d.png`), affiché à droite
  du bandeau sur plaque blanche (`Logo2`), mis à l'échelle en hauteur. Fichier absent → rien
  (pas de crash). `app/assets/README.txt` indique où déposer le PNG.
- NB : une image collée ne peut pas être écrite sur disque par l'assistant → l'utilisateur dépose
  le fichier lui-même.

### App + visu — sliders Transparence + Échelle mesh (carte Affichage)
- **Slider « Transparence de la carte »** (0-100 %) → opacité de la carte SPL (`map_opacity` via
  `cfg`), **re-rendu live**. Défaut 0 % (opaque). Remplace le choix opaque/fondu figé.
- **Slider « Échelle mesh (STL / BF) »** (0.50-1.50) → `factor` (échelle du mesh de référence vs
  grille BF). `factor` est **affichage seul** (uniquement dans `beamforming_visu`) → re-rendu **sans
  recalcul**. Retiré du pop-up avancé (qui ne garde que les offsets), persisté dans le projet.
- Nouveau widget `app/widgets/labeled_slider.py`. Câblage via `VIEW.opacity` + `refresh_view`.

### visu (fichier autorisé) — carte beamforming OPAQUE (visible en bartlett)
- L'opacité de la carte suivait le niveau (`0.95·SPL_norm`) → en **bartlett** (un seul pic), tout le
  hors-pic devenait **transparent** et on ne voyait que l'objet gris dessous. Carte passée en
  **opaque** (`opacity=1.0`) → le beamforming s'affiche **en plein** sur l'objet.
- (MUSIC s'affichait car niveaux élevés partout → déjà opaque.)

### App + visu — carte visible (PBR déplacé), viewport+sidebar suivent le thème, halo lumineux
- **Bug carte SPL invisible corrigé** : le PBR s'appliquait à la **surface colorée** (conflit avec
  l'opacité variable) → **déplacé sur l'OBJET** (STL gris). La carte redevient visible.
- **Viewport 3D + axes + colorbar suivent le thème** : fond clair en thème clair, sombre en sombre
  (`VIEW.set_theme`, appliqué à chaud). Idem aperçu scène.
- **Sidebar thème clair** : gris clair `#E7EBF1` (au lieu de navy), texte navy, logo sur plaque
  blanche ; reste navy en thème sombre.
- **Halo point chaud** : petite bille **auto-illuminée** (glow) + **vraie lumière ponctuelle chaude**
  à la source (au lieu de la grosse bille terne).
- **Vérifié** : compile, API `pv.Light`, sidebar claire (capture). Rendu 3D final à confirmer (OpenGL).

### App + visu — palette & effets 3D réglables (menu Affichage), turbo par défaut
- **Rendu pyvista paramétrable** : colormap (**turbo** par défaut), **SSAO** (occlusion ambiante),
  **PBR** (matériau satiné), **halo** sur le point chaud — tous lus depuis `cfg` (`beamforming_visu.py`,
  fichier autorisé). `add_mesh(cmap=…, pbr=…)`, `enable_ssao`, sphère-halo au max SPL.
- **Réglages partagés** `app/view_settings.py` (`VIEW`) ; **menu Affichage** : sous-menu *Palette*
  (turbo / jet / inferno / viridis) + cases *SSAO* / *PBR* / *Halo*. Appliqué **à chaud**
  (`refresh_view`, caméra conservée).
- **Vérifié** : compile, menu, wiring VIEW, API pyvista (enable_ssao, add_mesh pbr/smooth_shading).
  Le rendu final (turbo/effets) reste à confirmer à l'écran (OpenGL non capturable en headless) ;
  si le PBR assombrit trop, il se désactive dans le menu.

### App — champs épurés (fin des flèches spinbox) + Mesh STL lecture seule + rendu 3D lissé
- **Flèches up/down des spinbox supprimées** (vieillottes / mal alignées) → champs numériques épurés
  (saisie directe ; la fréquence garde son slider). Les combos gardent leur flèche déroulante.
- **Champ « Mesh STL » en lecture seule** (choix via *Parcourir…*) + style lecture seule distinct —
  l'édition texte du chemin n'avait pas de sens.
- **Rendu pyvista** : `smooth_shading` (surface lissée, plus de facettes) + anti-crénelage **FXAA**
  (`beamforming_visu.py`, fichier autorisé). API validée (pyvista 0.48.4).
- **Vérifié** via captures offscreen (formulaire sans flèches, combo avec flèche).

### App — refonte « à plat » alignée charte (fin du look 2010) + fixes
- **Refonte QSS plate / éditoriale** conforme à la charte : **suppression des dégradés**, rayons
  ramenés à **4-6 px**, **ombres teintées navy** (plus de noir), filets nets. (Mes dégradés/glows/
  gros arrondis faisaient justement « 2010 » et étaient hors charte.)
- **Fix « combo pas modifiable »** : la flèche déroulante avait disparu (`::drop-down` sur-stylé
  sans `::down-arrow`) → override retiré → **flèche native restaurée**, les menus (Mesure, Méthode)
  redeviennent clairement cliquables.
- **Fix « boutons qui tremblent au survol »** : retrait du **halo animé** sur les boutons ; le survol
  ne change que la couleur (aucun changement de taille) ; **focus champ en 1 px** (plus de saut).
- **Menu du haut** plus haut (padding 9 px) ; ombres cartes/bandeau navy sobres.
- **Vérifié** via captures offscreen (2 thèmes + combo avec flèche).

### App + visu — rendu 3D intégré (fond sombre), bandeau pro, effets au survol
- **Rendu pyvista sur fond sombre** dégradé (navy) assorti à l'UI, axes/grille + colorbar en
  **clair** → le 3D ne fait plus « ajouté » (fini le grand rectangle blanc). `beamforming_visu.py`
  (fichier autorisé) + aperçu scène côté `app/`.
- **Bandeau plus pro** : base **alignée** avec le bloc logo (filet rouge continu, hauteur 70),
  **titre + sous-titre discret** (fini l'eyebrow rouge).
- **Boutons d'action** : **halo rouge animé** au survol (`app/widgets/effects.py`, `QPropertyAnimation`).
- **Panneau résultat** : écart avec les étapes (fin du « collé ») + état vide plus soigné.
- **Vérifié** via captures offscreen (chrome 2 thèmes) ; le fond 3D sombre reste à confirmer à
  l'écran (rendu pyvista = OpenGL, non capturable en headless).

### src (exception autorisée pour ce fichier) — colorbar pyvista verticale à droite
- `beamforming_visu.py` / `plot_beamforming_3D_interactive_pyvista` : `add_mesh` reçoit
  `scalar_bar_args` (vertical, `position_x=0.88`, à droite) → la colorbar ne chevauche plus la
  grille d'axes du bas (`show_grid`).
- **Seul fichier hors `app/` modifié**, sur autorisation explicite de l'utilisateur pour ce fichier
  uniquement (la règle « rien hors `app/` » reste la norme). Paramètres validés (pyvista 0.48.4).

### App — corrections (bande du bas, panneau résultat, aide) + touche premium
- **Barre de progression** du bas : **masquée au repos** (fini la bande rouge parasite pleine),
  visible seulement pendant un calcul (mode indéterminé).
- **Panneau Résultat sans bordure** (`QFrame#ResultPanel`) : supprime le « cadre » que la colorbar
  pyvista chevauchait ; canvas inséré (marges). NB : la position colorbar/axes *dans* le rendu vient
  de `src/…/plot_beamforming` (hors `app/`, non modifiable par la règle app-only).
- **Aide développée** : *Guide d'utilisation* (dialogue `QTextBrowser`) — 3 étapes, navigation OBF,
  vues caméra, thèmes, projet, bouton Arrêter.
- **Premium** : léger **halo rouge** sous les boutons d'action (glow).
- **Vérifié** via captures offscreen (UI 2 thèmes + guide).

### App — bande de fréquence (2 poignées) + axes scène + effets modernes
- **Fréquence = BANDE [min, max]** : slider custom **à deux poignées** (`RangeSlider`, peint main)
  + saisies **min/max** synchronisées (`FreqBand`). `_fsel_min/_fsel_max` = bornes de la bande
  (défaut 1900–2100 Hz). Remplace le point unique.
- **Aperçu scène** : **axes gradués** (`show_bounds`, titres X/Y/Z en m) en plus du trièdre d'orientation.
- **Effets modernes** : dégradés (bandeau, sidebar, boutons Run, badges, onglet actif),
  **ombre portée** sous le bandeau (profondeur), piste/poignées stylées.
- **Vérifié** via captures offscreen (2 thèmes).

### App — ergonomie : accordéon (fin du scroll) + slider de fréquence
- Les **3 étapes** deviennent un **accordéon** (`CollapsibleCard`, une seule ouverte à la fois) →
  le panneau tient **sans scroll** ; **auto-avance** vers l'étape suivante après un calcul réussi.
- **Fréquence à traiter** = **slider + saisie synchronisés** (`FreqSlider`), borné à la plage CSM
  (étape 1), pas = `delta_f`. Remplace les 2 spinbox min/max ; fréquence unique → bande [f, f].
- Workflow `beamforming_run` : **snap au bin le plus proche** si aucun bin exact dans la bande
  (plus d'erreur bloquante) → le slider/saisie libre marche toujours.
- Slider stylé (piste + poignée rouge) ; nouveaux widgets `app/widgets/{collapsible,freq_slider}.py`.
- **Vérifié** via captures offscreen (accordéon + slider, 2 thèmes, sans scroll).

### App — logo CETIM en en-tête sidebar (délimité) + titre clarifié
- **Logo** déplacé dans un **en-tête de sidebar dédié** (plaque blanche + bordure basse) — top-left,
  bien délimité. Mis à l'échelle sur la **largeur** (lockup 4095×521, ratio ~7.9:1) pour tenir.
- **Bandeau épuré** : plus de logo ; eyebrow = page courante (majuscules), titre fixe
  **« Imagerie 3D · Antenne acoustique »**.
- Retrait du texte de marque ANTENNEMU / POSTE OFFLINE (redondant → « brouillon »).
- **Vérifié** via captures offscreen (logo net et cadré, bandeau clair).

### App — thèmes harmonisés (inspectés via captures offscreen)
- **Bug corrigé** : la règle `QWidget{background}` du thème écrasait `QLabel{background:transparent}`
  (même spécificité, déclarée après) → **tous les labels peignaient le fond de fenêtre** (invisible
  sur cartes blanches, mais boîte claire sur la sidebar navy en thème clair). Transparence des
  labels remise **en dernier** (`_TAIL` appliqué aux deux thèmes).
- **Bloc marque** : labels ajoutés directement au layout de la sidebar (plus de conteneur — un
  `QWidget`/`QFrame` intermédiaire ne se laissait pas rendre transparent).
- **Sombre** : contraste relevé — cartes/topbar/menu `#1A2C48` sur fond `#0B1626`, champs `#243B60`,
  bordures `#3A537C` → les surfaces se détachent nettement.
- **Méthode** : captures offscreen (`widget.grab()`) des deux thèmes + menu, inspectées pour ajuster
  (le rendu 3D pyvista, lui, exige un vrai contexte OpenGL).

### App — logo lisible sur fond sombre + vues caméra déplacées dans la carte 3
- **Logo CETIM** : plaque blanche arrondie en thème sombre (transparent en clair) → contraste OK.
- **Vues caméra** (Haut / Face / Gauche / Droite / Iso) déplacées du menu vers la **carte 3
  « Affichage »** (boutons Ghost qui appellent `set_view`).
- Menu **Affichage** ne garde que le choix de **thème**.
- **Vérifié (offscreen) :** compile, menus nettoyés, boutons de vue dans la carte 3, logo stylé.

### App — menu (Projet/Affichage/Aide), thèmes, logo CETIM, molette, matplotlib retiré
- **Molette** : les `QSpinBox`/`QComboBox` n'attrapent plus le scroll (sous-classes qui ignorent
  la molette sans focus) → on fait défiler le panneau sans modifier freq min/max par accident.
- **Scroll horizontal supprimé** sur le panneau d'étapes (`ScrollBarAlwaysOff`).
- **Logo CETIM** dans la barre supérieure (`data/assets/logo-cetim.png`, lu seul, hors `app/` non modifié).
- **Menu** : *Projet* (Ouvrir / Enregistrer / Enregistrer sous), *Affichage* (Thème Sombre/Clair +
  Vue caméra Haut/Face/Gauche/Droite/Iso), *Aide* (À propos).
- **Thèmes** sélectionnables (Sombre défaut / Clair) ; sidebar navy + console sombre communs.
- **matplotlib retiré** de la visualisation (pyvista uniquement) — champ « Visualisation » supprimé,
  `result_view` simplifié + `set_view()` (presets caméra).
- **Vérifié (offscreen) :** compile, logo chargé, menus, bascule de thème, `set_view`, molette,
  scroll horizontal off.

### App — thème sombre
- **Fond navy profond** `#0E1B2E`, **cartes surélevées** `#16273F` (ombre noire douce), champs
  `#1C2F4C` + menus/combos/déroulants assortis, texte clair `#E7EEF7`, accent rouge, focus bleu.
- Cases à cocher, scrollbars, tooltips, barre de progression et console de logs stylés dark.
- Statuts adaptés au fond sombre (vert `#3DD68C` / orange `#F5A623` / gris `#93A6C0`).
- **Vérifié (offscreen) :** compile + construction fenêtre OK.

### App — refonte visuelle moderne (cartes, barre supérieure, thème raffiné)
- **Barre supérieure** : eyebrow « CAMÉRA ACOUSTIQUE » + titre de page (suit la navigation) +
  actions **Projet** (Ouvrir / Enregistrer), filet rouge 3px. Ancien `menuBar` retiré.
- **Cartes** (`app/widgets/card.py`) : surface blanche, coins 12px, **ombre teintée navy**,
  en-tête **badge numéroté** + titre + sous-titre. Remplacent les `QGroupBox` (3 étapes + résultat).
- **Sidebar** : marque ANTENNEMU / POSTE OFFLINE + navigation (état actif rouge).
- **Thème raffiné** : bordures 1px, rayons 8-12px, focus bleu, boutons Run rouges / Ghost
  outline, **scrollbars fines**, **console de logs sombre**, espacements généreux.
- **Vérifié (offscreen) :** compile, fenêtre construite (topbar + sidebar + 4 cartes),
  navigation met le titre à jour, QSS appliqué.

### App — thème (charte), aperçu scène épuré, vue conservée en navigation OBF
- **Thème** : QSS aligné sur la charte — navy `#001E50` (encre), rouge `#EF3346` (accent),
  surfaces claires `#F4F6F9`/blanc, cyan/rose, gris froid ; **filet rouge 3px** sous le menu ;
  police Arial Nova ; sidebar navy, boutons « Run » rouges.
- **Aperçu scène** : rendu **dédié** (plus via `plot_beamforming`) — objet en **gris cadré en
  grand**, micros en **petits points rouges**, **sans colorbar** (matplotlib + pyvista).
- **Navigation OBF** : la **caméra** (vue 3D) est **conservée** entre sources (capture/restore),
  fini le reset à chaque ◀ ▶.
- **Vérifié (offscreen) :** compile, scène matplotlib (mesh + micros, sans colorbar),
  capture/restore de vue OK, thème appliqué.

### App — bouton Arrêter + antenne plus fine dans l'aperçu scène
- **Arrêter** : bouton dans la console de logs (actif seulement pendant un calcul ①/②) → tue
  le sous-processus (`QProcess.kill`). L'étape ne passe pas en « prête » (calcul interrompu).
- **Antenne** : l'aperçu scène force `sphere_radius=0.004` (défaut 0.025 → marqueurs énormes
  en matplotlib : `s=(r*1000)²=625`). Micros en petits points → maillage enfin visible.
- **Vérifié (offscreen) :** bouton actif pendant le run / désactivé sinon ; arrêt = pas de
  passage en « prêt ».

### App — lanceur `.bat` (double-clic)
- `app/lancer_app.bat` : lance l'appli en **double-clic**. Chemins **relatifs au `.bat`**
  (racine = parent de `app/`, python = `..\..\32\.venv`), donc portable si le tout est déplacé.
  Vérifie la présence du python du venv, `pause` sur erreur. (Un `.exe` demanderait PyInstaller
  — lourd à figer avec PySide6+pyvista+vtk ; le `.bat` suffit.)

### App — mesh par fenêtre, mémoire des chemins, aperçu scène, `n_sources` grisé
- **Mesh** : le champ « Mesh STL » devient un **sélecteur de fichier** (`.stl` ; défaut dans
  `data/data_mesh` → nom simple si dans ce dossier, sinon chemin absolu).
- **Mémoire des chemins** : les dialogues (dossier données, mesh) rouvrent au **dernier
  emplacement** utilisé (via `QSettings` — aucun fichier hors `app/`).
- **Aperçu scène** : bouton **« Afficher la scène (STL + antenne) »** → trace le maillage +
  les micros **avant** tout calcul (charge mesh + géométrie, rendu `plot_beamforming` à plat,
  `show_spheres=True`).
- **`n_sources`** : grisé si méthode = **bartlett** (utile seulement MUSIC/OBF).
- **Vérifié (offscreen) :** compile, `n_sources` grisé/actif selon méthode, mesh en picker,
  bouton scène présent, mémoire des chemins OK, projet 16 clés.

### App — fix ordre des `.dat` (index 0/1 inversé)
- **Bug :** le dropdown triait avec `sorted(glob.glob(...))` (chaînes, sensible à la casse)
  alors que `read_info.load_validation_data` trie avec `sorted(Path.glob("*.dat"))` (Path,
  insensible à la casse sous Windows) → l'index affiché ne correspondait pas au fichier
  réellement chargé (0 et 1 intervertis sur `DATA_SOURCE`).
- **Fix :** `DataSourceWidget` trie désormais avec `sorted(Path.glob("*.dat"))`, identique à
  `read_info` → l'index concorde. Vérifié : ordre du dropdown == ordre de `read_info`.

### App — OBF : navigation entre sources + affichage auto après beamforming
- **OBF multi-sources :** l'étape ② calcule et met en cache **toutes** les cartes (somme
  « Toutes les sources » + 1 carte par source/valeur propre) ; l'affichage propose des
  boutons **◀ ▶** pour naviguer entre sources **sans recalcul**. (② est donc plus long en OBF :
  `n_sources+1` passes de beamforming ; bartlett/music inchangés.)
- **Affichage auto :** après ② réussi, le graphe s'affiche **automatiquement** (par défaut
  **pyvista**, carte **combinée** — aucun mode présélectionné).
- **Vérifié (offscreen) :** flux 4 cartes OBF, navbar visible, navigation +/- avec wrap,
  rendu matplotlib OK.

### App — menu Projet, source par dropdown `.dat`, réglages avancés en pop-up
- **Projet** : menu « Projet » (Ouvrir / Enregistrer / Enregistrer sous) → sauvegarde et
  recharge tout l'état (paramètres + chemins) en `.json` (`get_project`/`load_project`).
- **Source de données** : dossier + **menu déroulant des `.dat`** (0, 1, 2… dans l'ordre de
  `sorted(glob("*.dat"))`, = le `chosen_index` de `read_info`), peuplé depuis le dossier choisi.
- **Condensé** : `factor` + offsets déplacés dans une pop-up « Réglages mesh avancés… » ;
  le formulaire principal ne garde que l'essentiel.
- **Vérifié (offscreen) :** compile, menu présent, round-trip projet OK, `Config` valide,
  dropdown peuplé depuis le dossier réel (3 mesures trouvées).

### App — fix affichage embarqué : réutilise `plot_beamforming` (rendu correct)
- **Problème :** la 1ʳᵉ version de l'embarqué **réimplémentait** un nuage de points → perdait
  le maillage reconstruit et le centrage sur l'objet (on voyait « les micros, pas centré »).
- **Fix :** on **réutilise `src.plot_beamforming`** (rendu exact : maillage triangulé, centrage,
  OBJ…) et on embarque sa sortie — matplotlib : la `Figure` dans un `FigureCanvas` (`plt.show`
  neutralisé le temps de l'appel) ; pyvista : `pv.Plotter` remplacé temporairement par un
  `QtInteractor` (pyvistaqt) pour construire **dans** le widget. Les `print` (dont la coche `✔`)
  sont capturés vers les logs (évite aussi le crash cp1252 de stdout).
- **Vérifié (offscreen) :** chemin matplotlib OK (figure embarquée via `plot_beamforming`, coche
  capturée). Chemin pyvista (`QtInteractor`) nécessite un écran → à tester en réel.

### App — affichage embarqué (matplotlib + pyvista) + logs en bas
- **Quoi :** l'étape ③ n'ouvre plus une fenêtre séparée : le résultat s'affiche **dans** le GUI
  (nuage de points du maillage coloré par le niveau dB + micros), au choix en **matplotlib**
  (FigureCanvas Qt, interactif) ou **pyvista** (QtInteractor via pyvistaqt) selon le paramètre
  « Visualisation ». Les **logs passent en bas** (QSplitter vertical). ① et ② restent en
  sous-processus ; ③ rend in-process. Nouveau widget `app/widgets/result_view.py` ;
  `plot_run.py` supprimé.
- **Deps :** `pyvistaqt` installé dans le venv (**non** ajouté au `pyproject`, hors `app/` —
  à faire plus tard). Liaison Qt unifiée (`QT_API=pyside6`, `MPLBACKEND=QtAgg`).
- **Vérifié (offscreen) :** compile, fenêtre construite, embed matplotlib OK. Le rendu pyvista
  (QtInteractor) nécessite un écran → à tester en réel.

### App — CSM précalculée sur une plage : changer la fréquence sans recalcul
- **Quoi :** l'étape ① précalcule la CSM sur une **plage** (`fmin`/`fmax` large) ; l'étape ②
  **choisit une fréquence/bande DANS cette plage** (`_fsel_min`/`_fsel_max`, filtre du cache) →
  changer la fréquence de beamforming ne recalcule plus la CSM. `diag_remove` déplacé en ①
  (il agit sur le calcul de la CSM).
- **Vérifié (offscreen) :** éditer la fréquence (param ②) conserve la CSM (`csm_ready` reste
  vrai, ② actif) ; seule ③ retombe. Params valides côté `Config` (clés `_fsel*` exclues).

### App — Beamforming en 3 étapes optimisées (cache de session)
- **Quoi :** la page Beamforming passe en 3 étapes : **① Charger + CSM** (le coûteux),
  **② Beamforming**, **③ Afficher**. Chaque étape écrit un cache `.npz` (dossier temporaire
  de session) que la suivante relit ; changer un param amont ré-invalide les étapes aval.
- **Pourquoi :** ne plus recharger le `.dat` + recalculer la CSM (FFT) à chaque tweak.
  Change le mesh/méthode → re-run **②③** ; change la visu → **③** ; change les fréquences → tout.
- **Archi :** 3 workflows sous-processus (`csm_run`, `beamforming_run`, `plot_run`) +
  `ParamForm.changed` qui pilote l'invalidation. Toujours **zéro modif de `src/`**.
- **Vérifié (offscreen) :** compile, se construit, machine à états correcte (boutons
  activés/désactivés selon ce qui est prêt, réutilisation de la CSM). Reste à tester en réel.

### App offline : nouvelle interface graphique (dossier `app/`)
- **Quoi :** appli PySide6 autonome (`app/`, lancée par `python -m app` depuis la racine)
  pour exécuter les workflows offline sans coder. **Squelette complet** (thème sombre,
  navigation latérale, console de logs) + **page Beamforming câblée** de bout en bout ;
  SPL/Puissance et Calibration en pages « à venir ».
- **Archi :** le GUI est un **lanceur PySide6 pur** ; chaque calcul tourne en
  **sous-processus** (`QProcess` → `app/workflows/beamforming_run.py`), équivalent CLI →
  aucun conflit de liaison Qt (PySide6 ↔ PyQt5/pyvista), UI non gelée, visu ouverte par
  l'enfant. **N'importe pas `src/live`** ; **ne modifie pas `src/`** (orchestration via
  `Config(overrides=...)`).
- **Vérifié (offscreen) :** 13 fichiers compilent, la fenêtre se construit, le process GUI
  ne tire aucun module lourd ni `src.live`, les fonctions `src` appelées existent.
- **À tester (toi) :** `python -m app` → onglet Beamforming → données + params → « Lancer »
  → logs + fenêtre 3D.

### Live allégé : `beamforming/__init__` paresseux + imports morts retirés
- **Quoi :** `beamforming/__init__.py` devient paresseux (PEP 562 `__getattr__`) — plus
  d'import en cascade des sous-modules de visu. `beamforming_signal` perd ses imports morts
  (`pandas`, `scipy.signal.spectrogram`, `stl`, et un `from src.visu import …` jamais utilisé).
- **Effet :** le chemin live (`live_processing` **et** `ui_qt`) ne charge plus **AUCUN**
  module lourd (avant : matplotlib, pyvista, vtk, numpy-stl, mpl_toolkits) → démarrage Qt
  allégé. Corrige aussi une violation de couche (compute `beamforming_signal` important la visu).
- **Vérifié :** live → 0 module lourd ; API offline intacte (`beamforming.run_beamforming_pipeline`
  / `plot_beamforming` résolus à la demande, import direct des Wrappers OK) ; 3 mains compilent.

### Dépendances : suppression de `requirements_antennemu.txt` (pyproject = source unique)
- **Quoi :** `requirements_antennemu.txt` supprimé ; `pyproject.toml` est la seule source
  des dépendances. Installation = `pip install -e .` (venv activé, depuis la racine).
- **Pourquoi :** le fichier doublonnait les `dependencies` du pyproject (risque de dérive).
  Commentaire du `pyproject.toml` mis à jour (ne référence plus le fichier supprimé).

### Config offline : cohérence légère (`config_calib` aligné sur `config`) + YAML en UTF-8
- **Quoi :** `config_calib.py` reçoit le même `Config(overrides=...)` validé que `config.py`
  (variante légère, **sans** base partagée — règle de trois : seulement 2 configs offline).
- **Encodage :** `config.yaml` réencodé cp1252 → UTF-8 (mojibake `�` corrigé) ; les `open()`
  de `config.py` passent en `encoding="utf-8"` → mêmes conventions que `config_calib`.
- **`config_live` : NON touché** (contexte appli Qt déployée, gardé séparé sur décision).
- **Vérifié :** valeurs de `config.py` identiques au baseline (réencodage neutre) ; override
  + validation typo OK sur les deux ; `main_CALIB` et mains cube compilent.

### Fix : erreurs « Exception ignored in __del__ » de PyVista à la fermeture
- **Quoi :** `PyVistaWrapper.show()` (`beamforming_visu.py`) ferme et désenregistre le
  plotter (`pv.close_all()` + `self.plotter = None`) dès que la fenêtre se ferme, et
  ignore un 2ᵉ appel (garde `if self.plotter is None`).
- **Pourquoi :** le `__del__` de PyVista appelle toujours `deep_clean()` ; si le Plotter
  survit jusqu'au shutdown (retenu par le registre global `_ALL_PLOTTERS`), ce
  `deep_clean` tourne après le démontage de VTK → `AttributeError 'NoneType'`. En lâchant
  les références tout de suite, le Plotter est collecté pendant que VTK est encore vivant.
- **Bonus :** neutralise le double `plotter.show()` des mains cube (fenêtre PyVista
  ouverte une seule fois). Matplotlib inchangé ; mains non touchées.
- **Vérifié :** confirmé par l'utilisateur (plus d'erreurs à la fermeture).

### Config : override propre depuis le main (params en Python) — pilote + réplication
- **Quoi :** `data/config.py` accepte `Config(overrides=dict)` : UNE construction qui
  valide les clés (clé absente de `config.yaml` → `KeyError` clair), applique les
  overrides, puis calcule les dérivés. Remplace `config = Config(); config.update(...)`
  (qui rechargeait le YAML + `setattr` silencieux → double source de vérité).
- **Mains migrés** (bloc `params_main` visible en tête, en Python, + `Config(overrides=...)`) :
  `main_BEAMFORMING_cube.py`, `main_BEAMFORMING_cube_ASPI.py`, `main_SPL_POWER_cube.py`.
- **config.yaml :** ajout de `df_band_bf` (seul param du main absent du registre),
  appendé en cp1252 (encodage du fichier) pour ne pas le corrompre.
- **Non touché :** `update()` (gardé pour compat), `config_calib`/`config_live`,
  `main_CALIB`/`main_pipeline`.
- **Vérifié :** syntaxe des 3 mains OK ; tous leurs params valident ; un typo lève une
  erreur explicite ; `Config()` par défaut inchangé.

### Nettoyage : retrait des artefacts vendorés de `ldsfdatareader`
- **Quoi :** suppression de `src/ldsfdatareader/{build,dist}` (dont l'installeur
  `.exe`) et du dossier imbriqué dupliqué `ldsfdatareader/ldsfdatareader/`.
- **Conservé :** `src/ldsfdatareader/__init__.py` — le SEUL fichier importé (via
  `import src.ldsfdatareader` dans `read_info`) — ainsi que `setup.py`/`README`/`install.bat`.
- **Vérifié :** `import src.read_info.read_info` OK avant ET après. Le `import
  ldsfdatareader` (top-level, ligne 6 du `__init__`) ne charge rien (échoue
  silencieusement) → le dossier imbriqué n'était pas nécessaire.

### Packaging : ajout de `pyproject.toml` — installable via `pip install -e .`
- **Quoi :** `pyproject.toml` minimal (setuptools) exposant `src` et `data` comme
  packages tels quels (rien déplacé) ; `.gitignore` ignore l'artefact `*.egg-info/`.
- **Pourquoi :** les imports `from src…` / `from data.config import Config`
  dépendaient du répertoire courant (cassaient hors de la racine). `pip install -e .`
  les rend valides depuis n'importe où.
- **Vérifié :** `pip install -e . --no-deps` OK ; un import lancé depuis `src/live/`
  (qui échouait avant) fonctionne désormais.
- **Note :** `requirements_antennemu.txt` était périmé (listait PyQt5 mais pas
  PySide6, et pas pyvista) ; **mis à jour** (ajout de PySide6 et pyvista aux versions
  du venv, regroupement par thème) en parallèle des `dependencies` du `pyproject.toml`.
  Reste à choisir une source de vérité unique (cf. backlog).

### Correctif : fuite matplotlib hors de la couche calcul — `2f9d5e1`
- **Quoi :** plus aucun module ne fait `matplotlib.use('Qt5Agg')`.
  - Couche calcul (`signal_process`, `beamforming_signal`, `beamforming_process`,
    `read_info`) : suppression des imports matplotlib morts.
  - Couche visu (`visu_plot`, `visu_interp`, `array`, `beamforming_visu`,
    `beamforming_mesh`, `power_acoustic`) : `matplotlib.use(...)` →
    `os.environ.setdefault("MPLBACKEND", "Qt5Agg")` (préférence, n'écrase pas un
    backend déjà choisi en amont).
  - `src/live/ui_qt.py` : suppression du monkeypatch `matplotlib.use = lambda: None` ;
    ne reste qu'un `os.environ.setdefault("MPLBACKEND", "Agg")` propre.
- **Pourquoi :** le backend doit être un choix d'application, pas un effet de bord de
  librairie (principe « functional core / imperative shell »). La vraie cause du leak
  est que `beamforming/__init__.py` importe en cascade les modules de visu.
- **Vérifié :** live → backend `Agg` (aucun binding Qt en double) ; offline → `Qt5Agg` ;
  import complet de `ui_qt` OK.

### Nettoyage : suppression du code legacy — `27cf528`
- Suppression de `trash/` (copies obsolètes) et de `main_Live32_newUI.py` (ancien
  point d'entrée live OpenCV, remplacé par `main_Live32_qt.py` / PySide6).
- `src/live/ui.py` (UI OpenCV) restauré : encore requis car `src/live/display.py`
  l'importe (utilisé par `ui_qt` pour `SHORTCUTS` et la gestion clavier).

### Commits de base (travail déjà présent) — `9102949`, `510f477`
- `9102949` : arrêt du suivi git des `.pyc` (déjà couverts par `.gitignore`).
- `510f477` : interface Qt/PySide6 + optimisations beamforming temps réel
  (cache `PlaneSteering`, LUT alpha, `cv2.remap`, blend in-place), modes
  d'acquisition Lent/Normal/Rapide, repli simulation, géométrie `32mu2.csv`.

---

## État actuel
- **Dépôt :** `ThibautGRAS/Code_Antenne` (GitHub, HTTPS) — branche `master`.
- **Convention config (offline)** : les mains cube/power suivent désormais un patron
  unique — bloc `params_main` en tête (Python) + `Config(overrides=...)` validé. Le
  reste de l'architecture (packages, autres points d'entrée) est inchangé.

## Backlog structurel (revue d'archi — NON fait, à planifier)
- [ ] **App offline (`app/`)** : brancher les pages SPL/Puissance et Calibration
      (Beamforming fait) ; workflows `app/workflows/spl_power_run.py` + `calibration_run.py`.
- [x] **Packaging** : `pyproject.toml` ajouté, `pip install -e .` fonctionnel (2026-06-28).
- [x] **requirements** : `requirements_antennemu.txt` supprimé ; `pyproject.toml` = source
      unique des dépendances. Install : `pip install -e .` (2026-06-28).
- [x] **Libs vendorées** : `src/ldsfdatareader/{build,dist}` + dossier imbriqué retirés (2026-06-28).
      Reste éventuellement `src/megamicros` (pilote MU32) à examiner — non touché ici.
- [x] **Config offline** : `config` + `config_calib` cohérents (`Config(overrides=...)`
      validé, YAML UTF-8). `config_live` gardé **séparé volontairement** (contexte appli Qt).
      Schéma dataclasses non fait — non prioritaire vu la philosophie « research ».
- [ ] **Points d'entrée** : unifier les `main_*` (idéalement via l'abstraction
      `src/pipelines/`, aujourd'hui inachevée).
- [x] **`beamforming/__init__.py`** : import paresseux (`__getattr__`) — le live ne tire
      plus aucun module lourd (matplotlib/pyvista/vtk/stl). Fait le 2026-06-28.
- [ ] **Retrait UI OpenCV** : découpler `ui_qt`/`display` de `ui.py` avant de
      pouvoir supprimer `ui.py`.
