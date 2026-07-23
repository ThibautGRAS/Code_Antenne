@echo off
title AntenneMu - Poste de travail (offline)

rem --- Chemins calcules par rapport a CE .bat (app\lancer_app.bat) ---
rem Racine du depot = dossier parent de app\
set "ROOT=%~dp0.."
rem Python du venv : AntenneMu\32\.venv\Scripts\python.exe (soit ..\..\32\.venv depuis app\)
set "PY=%~dp0..\..\32\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERREUR] Python du venv introuvable :
    echo    %PY%
    echo Adapte la variable PY dans ce .bat si le venv a change d'emplacement.
    echo.
    pause
    exit /b 1
)

cd /d "%ROOT%"
echo Lancement de l'application... ^(fermer la fenetre pour quitter^)
"%PY%" -m app

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application s'est terminee avec une erreur ^(voir ci-dessus^).
    pause
)
