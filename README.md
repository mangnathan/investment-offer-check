# investment-offer-check

**Vérifier, avant un virement vers un placement, qui sollicite le client.**

État : cadrage fixé, pas encore de code.

## Ce que fera l'outil

Un client reçoit une proposition de placement (courriel, conversation, brochure) et s'apprête à virer de l'argent. L'outil extraira de ce document qui le sollicite, vérifiera cette entité par le code dans les listes noires de l'AMF et les registres des acteurs autorisés, et produira une fiche de constats datés et sourcés. L'analyste fraude de la banque décide.

## Documents

- [Cadrage](docs/cadrage.md) : besoin, périmètre de la v1, données et contraintes juridiques, évaluation, seuils et critères d'arrêt, fixés avant toute mesure.

## Licence et indépendance

Code sous licence MIT, voir [LICENSE](LICENSE). Projet indépendant, sans lien avec l'AMF, l'ACPR ou la Banque de France. Aucune liste publique n'est republiée dans ce dépôt.

## Summary in English

Before a bank customer transfers money to an investment offer, the tool will read the document the customer received, extract who is soliciting them, and check that entity in code against public blacklists and registers of authorised firms. It will produce a dated, sourced evidence sheet; the bank's fraud analyst decides. Status: framing fixed, no code yet.
