# investment-offer-check

**Vérifier, avant un virement vers un placement, qui sollicite le client.**

État : cadrage fixé ; collecte des données publiques en cours d'écriture, analyse des documents pas encore écrite.

## Ce que fera l'outil

Un client reçoit une proposition de placement (courriel, conversation, brochure) et s'apprête à virer de l'argent. L'outil extraira de ce document qui le sollicite, vérifiera cette entité par le code dans les listes noires de l'AMF et les registres des acteurs autorisés, et produira une fiche de constats datés et sourcés. L'analyste fraude de la banque décide.

## Documents

- [Cadrage](docs/cadrage.md) : besoin, périmètre de la v1, données et contraintes juridiques, évaluation, seuils et critères d'arrêt, fixés avant toute mesure.

## Licence et indépendance

Code sous licence MIT, voir [LICENSE](LICENSE). Le fichier `src/investment_offer_check/suffixes/public_suffix_list.dat` est une copie non modifiée de la liste publique des suffixes, sous licence Mozilla Public License 2.0 (voir [sa provenance](src/investment_offer_check/suffixes/PROVENANCE.md)). Projet indépendant, sans lien avec l'AMF, l'ACPR ou la Banque de France. Aucune liste noire ni aucun registre n'est republié dans ce dépôt.

## Summary in English

Before a bank customer transfers money to an investment offer, the tool will read the document the customer received, extract who is soliciting them, and check that entity in code against public blacklists and registers of authorised firms. It will produce a dated, sourced evidence sheet; the bank's fraud analyst decides. Status: framing fixed; public-data collection being written, document analysis not written yet. The code is under the MIT licence; the copy of the Public Suffix List in `src/investment_offer_check/suffixes/` is unmodified and under the Mozilla Public License 2.0. No blacklist or register is republished in this repository.
