# Journal de travail — AntenneMu

> But : tracer les modifications (notamment celles faites avec Claude Code) pour
> reprendre le contexte rapidement. Ordre antéchronologique (le plus récent en haut).
> Convention : on note **quoi**, **pourquoi**, et le **hash de commit** quand il existe.

---

## 2026-06-28

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
- [ ] **requirements** : choisir une source de vérité unique entre
      `requirements_antennemu.txt` (à jour) et les `dependencies` du `pyproject.toml`
      (aujourd'hui dupliqués).
- [x] **Libs vendorées** : `src/ldsfdatareader/{build,dist}` + dossier imbriqué retirés (2026-06-28).
      Reste éventuellement `src/megamicros` (pilote MU32) à examiner — non touché ici.
- [~] **god-`Config`** : override propre fait sur `data.config` (`Config(overrides=...)`
      + validation des clés ; mains cube/power migrés). Reste : unifier les 3 classes
      `Config` et un schéma explicite (dataclasses) pour tuer les `getattr(..., default)`.
- [ ] **Points d'entrée** : unifier les `main_*` (idéalement via l'abstraction
      `src/pipelines/`, aujourd'hui inachevée).
- [ ] **`beamforming/__init__.py`** : stoppe l'import en cascade de la visu
      (lazy / `__getattr__`) pour que le live ne tire pas matplotlib.
- [ ] **Retrait UI OpenCV** : découpler `ui_qt`/`display` de `ui.py` avant de
      pouvoir supprimer `ui.py`.
