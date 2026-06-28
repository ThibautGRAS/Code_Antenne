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
