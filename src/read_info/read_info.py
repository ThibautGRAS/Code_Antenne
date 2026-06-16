# -*- coding: utf-8 -*-
"""
Created on Wed Apr  1 14:39:45 2026

@author: gras
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg')

from pathlib import Path
import glob

import src.ldsfdatareader as ldr

# ============================================================================
# UTILITAIRES Mmicro

def read_log_info(log_filename):
    info = {
        "Freq": None,
        "Duree": None,
        "Nb_ech": None,
        "Nb_micros_actifs": None,
    }
    
    with open(log_filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line.startswith("Freq"):
                temp = line.split("=")[1].split("(")[0]
                temp = temp.replace("   ;","")
                info["Freq"] = float(temp)

            elif line.startswith("Duree"):
                temp = line.split("=")[1].split("(")[0]
                temp = temp.replace("   ;","")
                temp = temp.replace(",",".")                
                info["Duree"] = float(temp)

            elif line.startswith("Nb_ech"):
                info["Nb_ech"] = int(line.split("=")[1])

            elif line.startswith("Nb_micros_actifs"):
                info["Nb_micros_actifs"] = int(line.split("=")[1])
                
            elif line.startswith("Nb_voies_analogiques"):
                info["Nb_voies_analogiques"] = int(line.split("=")[1])
                
            elif line.startswith("Nb_compteurs"):
                info["Nb_compteurs"] = int(line.split("=")[1])

    return info


def find_auto_file(folder: Path, base: str, num: int, extension: str):
    """
    Recherche automatiquement un fichier de type base<num>_*.extension
    """
    pattern = str(folder / f"{base}{num}_*.{extension}")
    matches = sorted(glob.glob(pattern))

    if len(matches) == 0:
        raise FileNotFoundError(f"Aucun fichier trouvé pour : {pattern}")
    if len(matches) > 1:
        print(f"⚠️ Plusieurs fichiers trouvés, premier pris : {matches[0]}")

    return Path(matches[0])

def load_band_corrections(config):
    """
    Charge le fichier *_mean_diff_per_band.txt et retourne :
    - bands_corr : fréquences centrales des bandes
    - diff_corr  : différences moyennes associées
    """

    # Construction du chemin complet vers le fichier
    corr_file = config.calib_file

    bands_corr = []
    diff_corr = []

    with open(corr_file, "r", encoding="utf-8") as f:
        next(f)  # saute l'en-tête
        for line in f:
            fc, d = line.split()
            bands_corr.append(float(fc))
            diff_corr.append(float(d))
            
    print(f"\nFichier selectionne : config.calib_file")

    return np.array(bands_corr), np.array(diff_corr)


def load_validation_data(config, file_dat=None):
    """
    Charge un fichier .dat de validation, lit le .log associé,
    met à jour les paramètres du config,
    et retourne le signal Sigs_val (NbVoies x N_ech).

    Parameters
    ----------
    config : Config
        Objet de configuration.
    file_dat : Path | str | None
        Si None, charge le fichier via config.chosen_index dans
        config.validation_folder.
        Sinon, charge directement ce fichier.

    Returns
    -------
    Sigs_val : np.ndarray
        Tableau des signaux, shape (NbVoies, N_ech).
    config : Config
        Config mis à jour.
    """
    from pathlib import Path
    import numpy as np

    # ------------------------------------------------------------------
    # Cas 1 : sélection automatique via chosen_index
    # ------------------------------------------------------------------
    if file_dat is None:
        dat_files = sorted(config.validation_folder.glob("*.dat"))

        if not dat_files:
            raise FileNotFoundError(
                f"Aucun fichier .dat trouvé dans {config.validation_folder}"
            )

        print("Fichiers disponibles dans le dossier :")
        for i, f in enumerate(dat_files):
            print(f"[{i}] {f.name}")

        file_dat = dat_files[config.chosen_index]
        print(f"\nFichier sélectionné : [{config.chosen_index}] {file_dat.name}")

    # ------------------------------------------------------------------
    # Cas 2 : fichier imposé
    # ------------------------------------------------------------------
    else:
        file_dat = Path(file_dat)

        if not file_dat.exists():
            raise FileNotFoundError(f"Fichier .dat introuvable : {file_dat}")

        print(f"\nFichier sélectionné : {file_dat.name}")

    # ------------------------------------------------------------------
    # Lecture du .dat
    # ------------------------------------------------------------------
    with open(file_dat, "rb") as fid:
        data_val = np.fromfile(fid, dtype="int32")

    # ------------------------------------------------------------------
    # Lecture du .log associé si disponible
    # ------------------------------------------------------------------
    logfile = file_dat.with_suffix(".log")
    
    if logfile.exists():
        log_info = read_log_info(logfile)
    
        # Mise à jour du config uniquement si l'info existe
        if log_info.get("Freq") is not None:
            config.Fe = log_info["Freq"]
    
        if log_info.get("Duree") is not None:
            config.duration = log_info["Duree"]
            
        if log_info.get("Nb_ech") is not None:
            config.nb_ech = log_info["Nb_ech"]
    
        if log_info.get("Nb_micros_actifs") is not None:
            config.NbMems = log_info["Nb_micros_actifs"]
    
        if log_info.get("Nb_voies_analogiques") is not None:
            config.Nbanalogique = log_info["Nb_voies_analogiques"]
    
        if log_info.get("Nb_compteurs") is not None:
            config.Nbcompteur = log_info["Nb_compteurs"]
    
        print(f"[OK] Fichier .log lu : {logfile.name}")
    
    else:
        print(f"⚠️ Pas de fichier .log associé, on garde les paramètres déjà présents dans config : {file_dat.name}")
    
    # ------------------------------------------------------------------
    # Vérification des champs nécessaires
    # ------------------------------------------------------------------
    required_attrs = ["Fe", "NbMems", "Nbanalogique", "Nbcompteur"]
    
    missing = [attr for attr in required_attrs if not hasattr(config, attr)]
    if missing:
        raise AttributeError(
            f"Le fichier .log est absent/incomplet et les attributs suivants manquent dans config : {missing}"
        )
    
    # ------------------------------------------------------------------
    # Nombre total de voies
    # ------------------------------------------------------------------
    config.NbVoies = config.NbMems + config.Nbcompteur + config.Nbanalogique

    # ------------------------------------------------------------------
    # Vérification cohérence taille
    # ------------------------------------------------------------------
    if data_val.size % config.NbVoies != 0:
        raise ValueError(
            f"Taille incohérente : {data_val.size} valeurs pour {config.NbVoies} voies."
        )

    # ------------------------------------------------------------------
    # Reshape
    # ------------------------------------------------------------------
    Sigs_val = data_val.reshape((-1, config.NbVoies)).T

    # ------------------------------------------------------------------
    # Si la durée n'est pas définie, on la calcule automatiquement
    # ------------------------------------------------------------------
    if getattr(config, "duration", None) is None:
        config.duration = Sigs_val.shape[1] / config.Fe
        print(f"⚠️ Durée absente dans le .log → durée calculée = {config.duration:.3f} s")
          
    print("[OK] Données de validation chargées")
    print(f"  • Fe = {config.Fe} Hz")
    print(f"  • Durée = {config.duration} s")
    print(f"  • Nb MEMS = {config.NbMems}")
    print(f"  • Nb voies = {config.NbVoies}")
    print(f"  • Shape Sigs_val = {Sigs_val.shape}")

    return Sigs_val, config

def load_reference_microphones(file_ldsf, micro_channels):
    """
    Charge les voies micro de référence depuis un fichier LDSF.

    Returns
    -------
    micros_dict : dict
        {
            ch: {
                'time': np.ndarray,
                'signal': np.ndarray,
                'fs': int
            }
        }
    """
    

    micros_dict = {}

    with ldr.open(str(file_ldsf)) as ldsf:
        for ch in micro_channels:
            sr = ldsf[ch].series()
            micros_dict[ch] = {
                "time": sr.index.values,
                "signal": sr.values,
                "fs": int(ldsf[ch].sample_rate)
            }

    return micros_dict

def load_geo_positions(config):
    """
    Lit le fichier GEO défini dans config.geo_file,
    affiche le nom du fichier et la taille du tableau,
    et retourne un tableau NumPy des positions (X, Y, Z).
    """

    # Lecture du fichier GEO
    geo_df = pd.read_csv(config.geo_file, sep=';')
    geo_positions = geo_df[['X', 'Y', 'Z']].values

    # Affichage des infos
    print(f"\n[OK] Fichier GEO charge : {config.geo_file.name}")
    print(f"Taille des positions : {geo_positions.shape[0]} points (X, Y, Z)")

    return geo_positions