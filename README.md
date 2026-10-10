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

Dans Aurora : `F7` → onglet **Other** → **3rd Party Software Access** → **Yes**.
Dans **Configuration** de l'appli, renseigner l'adresse (en général `127.0.0.1`)
et le port **1130**, puis associer chaque position à ses codes OACI (séparés par
des virgules).

Le protocole réel d'Aurora est ASCII, en TCP, avec des commandes au format
`#COMMANDE;champ1;champ2;...` terminées par CR/LF (doc officielle IVAO :
*Aurora 3rd Parties Documentation*). L'appli interroge périodiquement `#TR`
(trafic en vue), puis `#FP;CALLSIGN` (plan de vol) et `#TRPOS;CALLSIGN`
(position/altitude) pour chaque indicatif. Cette couche est isolée dans
`stripboard/aurora.py` afin de pouvoir l'adapter facilement si le protocole
évolue.

## Tableau ADI/ENAC

Pour les positions associées à un aéroport pris en charge (Toulouse-Blagnac
pour l'instant, d'autres à venir), l'appli bascule automatiquement sur un
tableau de strips au format ADI/ENAC avec alignement conditionnel sur les
pistes. Détails dans [docs/ADI_BOARD.md](docs/ADI_BOARD.md).

## Tests

```bash
python -m unittest discover -s tests -v
```
