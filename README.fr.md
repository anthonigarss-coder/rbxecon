# rbxecon

Simule l'économie d'un tycoon Roblox **avant** de la mettre dans le jeu, puis exporte les mêmes chiffres en Luau.

Tu décris tes objets (prix, revenu, hausse de prix, prérequis, multiplicateurs) dans un fichier TOML. `rbxecon` joue à ta place avec trois types de joueurs et te dit :

- combien de temps il faut pour tout acheter,
- où le joueur attend trop (**zones mortes**),
- si tes **objectifs de rythme** sont tenus (« le Sauna doit arriver vers la minute 20 »).

Ensuite `rbxecon luau` écrit un module `Economy.luau` : le jeu et la simulation utilisent les mêmes chiffres.

Aucune dépendance. Python 3.12+. Licence MIT.

## Installer

```bash
git clone https://github.com/anthonigarss-coder/rbxecon
cd rbxecon
uv sync          # ou : pip install .
uv run rbxecon init economy.toml
```

## Utiliser

```bash
rbxecon init economy.toml          # écrit un exemple
rbxecon check economy.toml         # cherche les erreurs
rbxecon sim economy.toml           # simule (toutes les stratégies)
rbxecon sim economy.toml -s roi --timeline 20
rbxecon sim economy.toml --json --csv run.csv --svg graphe.svg
rbxecon luau economy.toml -o Economy.luau
```

Codes de sortie : `0` ok, `1` objectif raté ou erreurs de config, `2` entrée invalide.

Stratégies : `roi` (achète ce qui se rentabilise le plus vite), `cheapest` (le moins cher d'abord), `order` (dans l'ordre du fichier). Un vrai joueur est entre `roi` et `cheapest`.

Le format du fichier de config est détaillé dans le [README anglais](README.md) et dans l'exemple généré par `rbxecon init`. Les chiffres de l'exemple sont des **exemples** : remplace-les par ceux de ton jeu.

## Export Luau

```lua
local Economy = require(ReplicatedStorage.Economy)
Economy.getCost("Treadmill", 3)     -- prix de la prochaine copie quand on en a 3
Economy.isUnlocked("Bench", owned)  -- prérequis remplis ?
Economy.incomePerSecond(owned)      -- groupes + multiplicateurs
```

`owned` = table `{ [nomObjet] = quantité }`.

Le Luau généré est testé sur son texte seulement, pas exécuté dans un moteur Luau par l'auteur. Vérifie une fois dans Studio avec le test donné dans le README anglais.

## Tests

```bash
uv run pytest
```

## Licence

MIT
