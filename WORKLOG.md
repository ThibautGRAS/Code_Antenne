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
