# Notebook 13 — Partial-order analysis, en bref

Un guide minimal pour comprendre ce que fait le notebook et pourquoi.

---

## 1. Le problème

Le notebook 09 calcule **un seul score** par groupe : Citizens = +57, Women = −21, etc. C'est une **projection sur une ligne**.

Problème : si Women ont plus de richesse matérielle que Slaves, mais Slaves ont plus de droits légaux que Women, **aucun des deux ne domine l'autre**. Un score unique le cache.

L'ordre partiel garde cette information.

---

## 2. La donnée de base : un profil-signe

Pour chaque groupe `g` et chaque type de ressource `r` (8 axes : Bodily Autonomy, Legal Standing, Material Wealth, …), on calcule

```
net(g, r) = (# règles MORE) − (# règles LESS)
```

puis on garde juste le signe :

| `net` | profil |
|---|---|
| > 0 | **+1** (le groupe a un accès net positif à cet axe) |
| < 0 | **−1** (accès net négatif) |
| = 0 | **0** (rien attesté, ou équilibré) |

Chaque groupe devient donc un **vecteur de 8 signes**. Exemple :

```
Citizens : [+1, +1, 0, −1, +1, +1, +1, −1]
Women    : [−1, −1, 0, +1,  0, +1, −1, −1]
```

---

## 3. La règle de domination

> **A domine B** (`A ≽ B`) si pour **chaque** axe, `signe(A) ≥ signe(B)`.

C'est tout. Composante par composante, avec `−1 < 0 < +1`.

Trois cas possibles pour chaque paire :
- **A domine B** (A est ≥ partout, et > sur au moins un axe) → A est strictement au-dessus.
- **B domine A** (symétrique).
- **Incomparable** : A est meilleur sur certains axes, B sur d'autres. **Aucun n'est au-dessus.**

C'est l'incomparabilité qui est nouvelle : un score unique ne peut pas la représenter.

---

## 4. Les outils qu'on en tire

### Diagramme de Hasse
Un graphe où une flèche `A → B` veut dire "A domine directement B" (sans intermédiaire).
- Lecture : plus haut = domine, mêmes lignes sans flèche = incomparables.
- On le dessine **par période** pour voir comment la structure change.

### Hauteur (height)
La plus longue chaîne de dominations : `A ≻ B ≻ C` a hauteur 3.
- **Grande hauteur** = société en échelle, beaucoup de niveaux empilés.
- **Petite hauteur** = peu de hiérarchie verticale.

### Largeur (width)
Le plus grand groupe de personnes **mutuellement incomparables**.
- **Grande largeur** = plusieurs axes de statut parallèles, qui ne se réduisent pas à une seule échelle.
- **Petite largeur** = tout le monde sur la même échelle.

> Calcul : on utilise le **théorème de Dilworth** — la largeur est égale au nombre minimum de chaînes pour couvrir tout l'ordre, qui se calcule par couplage maximum bipartite.

### Diff entre périodes
Pour chaque paire de périodes consécutives, on compare les arêtes de Hasse :
- **gardées** : arêtes présentes dans les deux périodes (hiérarchies stables).
- **perdues** : arêtes qui disparaissent (effondrement d'une domination).
- **gagnées** : nouvelles arêtes (apparition d'une nouvelle domination).

### Table d'incomparabilités
Pour chaque paire incomparable, on liste **sur quels axes A bat B** et **sur quels axes B bat A**. C'est là que le score unique de notebook 09 perd le plus d'information.

---

## 5. Ce qu'on a trouvé sur le corpus

| Structure | Résultat |
|---|---|
| Ordre global | **large et plat** — largeur 6, hauteur 2 |
| Arêtes stables entre toutes les périodes | **une seule** : Citizens ≻ Foreigners |
| Arêtes Classique → Late Classique | **0 gardées**, 6 perdues, 4 gagnées (réorganisation totale) |
| Largeur dans le temps | 4 → 6 → 6 → 3 (s'élargit puis se contracte sous Rome) |

Conclusion synthétique : le statut dans le corpus gréco-romain est **multidimensionnel et instable**. Une seule domination survit clairement à travers les siècles ; tout le reste est volatile et pluriel.

---

## 6. Limites à garder en tête

1. **Seuil = 0.** On bascule du négatif au positif au moindre déséquilibre. Un seuil plus prudent (`|net| ≥ 2`) donnerait moins d'arêtes mais plus robustes.
2. **Petits échantillons.** Les groupes avec ~5 règles peuvent flipper de signe à chaque règle ajoutée — une partie de la "volatilité entre périodes" est probablement du bruit. Un bootstrap permettrait de quantifier.
3. **Pas de pondération entre axes.** L'ordre considère les 8 ressources comme également importantes. C'est un choix : on cherche les dominations qui tiennent **quel que soit le poids** qu'on donne à chaque axe.

---

## TL;DR

Au lieu de demander **"qui est plus privilégié ?"** (un score), on demande **"qui est plus privilégié sur quoi ?"** (un vecteur), puis on regarde, paire par paire, si un vecteur en contient un autre. Ce qui n'est *pas* dominé est *incomparable* — et c'est cette incomparabilité qui dit quelque chose de structurel sur la société.
