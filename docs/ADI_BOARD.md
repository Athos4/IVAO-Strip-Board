# Tableau de strips ADI/ENAC

Ce document décrit le mode « tableau de strips » ajouté au-dessus de la vue
grille existante. Il reproduit la disposition et le format de strip utilisés
sur les tableaux ADI (French ATC) inspirés des supports pédagogiques ENAC.

**Seul l'aéroport de Toulouse-Blagnac (LFBO) est implémenté pour l'instant.**
D'autres aéroports arriveront progressivement : chaque terrain nécessite un
profil dédié (pistes, altitude de terrain, organisation des catégories du
tableau) décrit plus bas, donc le travail d'ajout est volontairement
incrémental.

## Activation

Le tableau de strips remplace automatiquement la grille classique dès que la
position sélectionnée est associée à un aéroport pour lequel un profil existe
(aujourd'hui : `LFBO`). Sinon, l'application retombe sur la grille 4×8
classique.

## Profils d'aéroport (`stripboard/airport.py`)

Un `AirportProfile` décrit :
- la liste des pistes (`Runway`), avec leurs identifiants dans les deux sens
  (`near_identifier` / `far_identifier`) et un indicateur FATO pour les
  hélicoptères ;
- l'altitude de terrain (`elevation_ft`), utilisée pour déterminer si un
  strip doit encore apparaître sur le tableau (`FlightStrip.is_airborne`) ;
- un indicateur `verified` pour signaler les profils non encore validés.

`profile_for(icao)` retourne le profil correspondant ou `None`. Pour ajouter
un nouvel aéroport, il suffit d'ajouter une entrée dans `PROFILES`.

## Disposition du tableau (`stripboard/board.py`)

Le tableau comporte 15 lignes réparties sur deux colonnes :
- **colonne de gauche** : arrivées IFR non identifiées, VFR en plan de vol,
  hélicoptères en attente de roulage, etc. ;
- **colonne de droite** : trafic en transit, trafic en vol hors circuit, trafic
  dans le circuit non autorisé à l'atterrissage, puis une ligne par piste du
  profil (avec une case « taxiway » avant les pistes qui le nécessitent), et
  enfin une case « point d'attente ».

Chaque ligne piste (`kind="runway"`) est la zone où s'effectue l'alignement
conditionnel (voir plus bas).

## Format du strip

Chaque strip reprend les proportions réelles d'un strip ADI (242 mm de large)
réparties en 6 blocs :

1. **Identification** — indicatif, type d'avion + catégorie de turbulence de
   sillage (calculée automatiquement via `stripboard/wake_turbulence.py`),
   aéroports départ/arrivée, règles de vol, transpondeur assigné ou affiché
   selon la phase de vol.
2. **Barre couleur** — rouge pour un départ, bleu pour une arrivée, les deux
   empilées pour un tour de piste.
3. **Route / coordination / point d'attente** — le repère de procédure prévu
   en haut, une zone de coordination éditable en bas à gauche, et une case
   dédiée au point d'attente en bas à droite.
4. **Niveaux / ATIS / TWY / Poste** — niveau assigné, lettre ATIS (menu
   déroulant A→Z), poste de stationnement.
5. **Archive** (grille 2×2) — EOBT (départ) ou ETA (arrivée) en lecture
   seule, piste assignée (menu déroulant), heure de décollage et heure de
   premier/dernier contact (saisie libre).
6. **Secteur / règles** — aéroport de rattachement et règles de vol.

## Champs interactifs

Les cases suivantes sont cliquables :

| Case | Interaction | Valeur |
|---|---|---|
| Piste assignée (bloc 5) | menu déroulant | pistes du profil aéroport |
| ATIS (bloc 4) | menu déroulant | lettres A à Z |
| Heure de décollage (bloc 5) | saisie clavier | texte libre |
| Heure de contact (bloc 5) | saisie clavier | texte libre |
| Zone de coordination (bloc 3) | saisie clavier | texte libre |
| Point d'attente (bloc 3) | saisie clavier | texte libre |

Un clic ouvre le menu ou un champ de saisie positionné exactement sur la
case ; `Entrée` ou perte de focus valide, `Échap` annule.

Les valeurs saisies manuellement sont mémorisées (`StripBoard.manual_fields`)
et réappliquées à chaque rafraîchissement Aurora, pour ne pas être écrasées
par les mises à jour `#FP`/`#TRPOS` suivantes.

## Alignement conditionnel

Reproduit le principe ADI/ENAC : *« le strip de l'aéronef dont le départ est
conditionné par le dégagement de piste de l'arrivée est toujours positionné
dessous »*.

- Glisser un strip sur une case piste déjà occupée **en maintenant Shift**
  l'aligne sous le strip déjà présent. Sans Shift, le dépôt est refusé
  (« Case déjà occupée ») comme auparavant.
- Le strip du dessous reste entièrement visible via son identité (bloc 1 +
  barre couleur) qui dépasse à gauche ; le strip du dessus est dessiné par
  dessus, décalé à droite, avec sa propre barre couleur dans son
  emplacement habituel.
- Tant que deux strips sont liés, l'édition de leurs champs (piste, ATIS,
  heures, coordination, point d'attente) est bloquée pour éviter toute
  modification accidentelle pendant que l'alignement conditionnel est actif.
- Déplacer ou archiver le strip du dessus libère automatiquement le strip du
  dessous, qui reprend sa propre case normalement.
- Un strip ne peut être lié qu'une seule fois (pas de chaîne à trois strips).

## Fichiers concernés

- `stripboard/airport.py` — profils d'aéroport et pistes.
- `stripboard/board.py` — disposition des 15 lignes du tableau.
- `stripboard/wake_turbulence.py` — catégorie de turbulence de sillage par
  type d'avion ICAO.
- `stripboard/models.py` — champs du strip (EOBT, ATIS, coordination, point
  d'attente, etc.) et `Placement.under` pour l'alignement conditionnel.
- `stripboard/app.py` — rendu du tableau, champs interactifs, glisser-déposer
  et logique d'alignement conditionnel.
