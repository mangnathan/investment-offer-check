# Liste publique des suffixes

`public_suffix_list.dat` est une copie non modifiée de la liste publique des suffixes, qui sert à trouver le domaine enregistrable d'un nom (`exemple.co.uk`, `faux-conseil.wixsite.com`). Elle est copiée dans le dépôt pour qu'aucune exécution ne la télécharge.

- Adresse officielle : https://publicsuffix.org/list/public_suffix_list.dat
- Version : `2026-11-27_12-48-40_UTC`, commit `73edc270543c9a079e6a21f310adc5744ee7c20d` (lignes VERSION et COMMIT de l'en-tête)
- Téléchargée le 28 novembre 2026
- SHA-256 : `e2ec22b08f0ea2104c850e8d52be113ec3729621696356b7436e96ca67ec6837`
- Licence : Mozilla Public License 2.0, indiquée dans l'en-tête du fichier, conservé tel quel. Le reste du dépôt est sous licence MIT.
- Les deux parties de la liste sont utilisées : les suffixes publics délégués par l'ICANN et les suffixes privés déclarés par des hébergeurs.

Les cas de test officiels (`tests/donnees/test_psl.txt`, versés au domaine public, CC0) viennent de https://raw.githubusercontent.com/publicsuffix/list/master/tests/test_psl.txt, téléchargés le même jour (SHA-256 `8f50ad958916d6a8f79fba2363501475571acce752757f9126fe9d2f17dd920d`).

## Mise à jour

La liste change quelques fois par semaine ; une mise à jour par mois suffit pour la collecte.

1. Télécharger le fichier depuis l'adresse officielle, et seulement celle-là.
2. Vérifier que l'en-tête contient toujours la licence et les lignes VERSION et COMMIT.
3. Remplacer le fichier sans le modifier, et mettre à jour la version, la date et le SHA-256 ci-dessus.
4. Lancer les tests : les cas officiels doivent tous passer.
5. Commiter seul, avec la nouvelle version dans le message.
