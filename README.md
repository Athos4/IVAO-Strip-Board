# IVAO Strip Board

Petit tableau de strips de bureau pour Windows, inspiré des tableaux français et
alimenté par l'interface TCP « third party » d'Aurora.

## Fonctionnalités

- grille de **4 colonnes × 8 lignes** ;
- arrivée automatique des strips non traités dans la quatrième colonne ;
- glisser-déposer dans une case et double-clic permettant d'occuper une ou deux colonnes ;
- filtrage par position contrôlée et par liste d'aéroports ;
- sauvegarde de la configuration et de la disposition dans le profil utilisateur ;
- connexion TCP asynchrone et simulateur intégré pour tester sans Aurora.

## Lancer

Python 3.11+ suffit (Tkinter est inclus dans l'installation Windows officielle).

```bash
python -m stripboard
```

Sous Windows, `run_stripboard.bat` permet aussi de lancer l'application sans
terminal. Pour créer un exécutable autonome :

```powershell
py -m pip install pyinstaller
pyinstaller --noconsole --onefile --name IVAO-Strip-Board stripboard/__main__.py
```

## Connexion Aurora

Dans **Configuration**, renseigner l'adresse et le port exposés par le module
third-party d'Aurora, puis associer chaque position à ses codes OACI (séparés par
des virgules). L'adaptateur attend un objet JSON par ligne ; un strip ressemble à :

```json
{"type":"strip","callsign":"AFR123","departure":"LFPG","arrival":"LFPO","aircraft":"A320","route":"OKIPA DCT","level":"FL120"}
```

`type: "delete"` avec un `callsign` retire un vol. Les champs usuels `dep`,
`dest`, `adep`, `ades`, `flight_level` et `assigned_level` sont également
acceptés. Cette couche est isolée dans `stripboard/aurora.py` afin de pouvoir
adapter facilement le mapping à la version exacte de l'interface Aurora.

## Tests

```bash
python -m unittest discover -s tests -v
```
