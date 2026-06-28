# Journal de travail — AntenneMu

> But : tracer les modifications (notamment celles faites avec Claude Code) pour
> reprendre le contexte rapidement. Ordre antéchronologique (le plus récent en haut).
> Convention : on note **quoi**, **pourquoi**, et le **hash de commit** quand il existe.

---

## 2026-06-28

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
- **Structure non modifiée :** seuls des correctifs *intra-fichiers* + du nettoyage
  ont été faits. L'architecture (packages, points d'entrée, `Config`) est intacte.

## Backlog structurel (revue d'archi — NON fait, à planifier)
- [x] **Packaging** : `pyproject.toml` ajouté, `pip install -e .` fonctionnel (2026-06-28).
- [ ] **requirements** : choisir une source de vérité unique entre
      `requirements_antennemu.txt` (à jour) et les `dependencies` du `pyproject.toml`
      (aujourd'hui dupliqués).
- [ ] **Libs vendorées** : retirer `src/ldsfdatareader/{build,dist}` (+ le `.exe`).
- [ ] **god-`Config`** : 3 classes `Config` + `getattr(..., default)` partout →
      schéma explicite (dataclasses par domaine).
- [ ] **Points d'entrée** : unifier les `main_*` (idéalement via l'abstraction
      `src/pipelines/`, aujourd'hui inachevée).
- [ ] **`beamforming/__init__.py`** : stoppe l'import en cascade de la visu
      (lazy / `__getattr__`) pour que le live ne tire pas matplotlib.
- [ ] **Retrait UI OpenCV** : découpler `ui_qt`/`display` de `ui.py` avant de
      pouvoir supprimer `ui.py`.
