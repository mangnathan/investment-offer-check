# Cadrage : vérifier qui sollicite un client avant un virement vers un placement

Version du 27 novembre 2026. Ce document est commité avant toute ligne de code et avant toute mesure. Les seuils et les critères d'arrêt qu'il fixe ne sont plus modifiés une fois la mesure commencée ; un changement passe par un nouveau commit qui en donne la raison, et les résultats sont alors rapportés avec l'ancien et le nouveau seuil.

Les sources sont numérotées entre crochets et listées à la fin.

## Modifications

- 28 novembre 2026, avant toute mesure : la décision prévue par le critère d'arrêt 1 est avancée, car l'accès à des documents réels est jugé improbable dans les délais. L'évaluation des documents porte sur des documents fabriqués ; seuls les documents réels deviennent un bonus, mesuré à part s'il en arrive. Le jeu local garde les documents fabriqués à partir de vraies entrées de la liste de l'AMF, et tous les seuils, ceux du jeu local et ceux des deux jeux compris, restent inchangés.

## Résumé des décisions

1. Le cœur du projet est le niveau 2 : lire ce que le client a reçu, en extraire qui le sollicite, puis vérifier cette entité par du code. Le modèle de langage sert seulement à l'extraction.
2. Le niveau 1 est un filtre rapide et bon marché, présenté comme tel. L'argent part souvent vers des comptes de tiers ou vers le propre compte du client chez une plateforme agréée ; son rappel réel est mesuré et publié, même faible.
3. L'outil complète le fichier national des comptes signalés, qui ne connaît que les IBAN déjà signalés. Il vise les entités et les marques qui sollicitent le client et qui ne sont pas encore reliées à un IBAN signalé.
4. La v1 ne traite que du texte : exports de conversations, courriels, PDF textuels. Les captures d'écran viennent en v2 ou plus tard, avec leur propre évaluation.
5. Le périmètre de la v1 est gelé à la fusion de ce cadrage, et la v1 est livrée au plus tard le 31 janvier 2027. Ce qui n'est pas prêt à cette date passe en v2.
6. La v2 est engagée : agent comparé au flux fixe, outils exposés par MCP en local, injections propres à l'agent.
7. Aucune liste n'est versionnée ni republiée : les données sont téléchargées à l'exécution. Il n'y a pas de branche de données publique en v1, car une liste de domaines datés republierait la liste de l'AMF et exposerait à un risque de diffamation ; seuls des agrégats sont publiés, et la question est rouverte en v2.
8. La v1 est mesurée sur le test rétrospectif 2026, ouvert une seule fois. Le jeu prospectif issu de la collecte quotidienne est évalué en v2, faute d'effectifs suffisants fin janvier.
9. Chaque seuil est jugé sur la borne de l'intervalle de confiance à 95 % la moins favorable, pas sur la valeur centrale.
10. L'évaluation des documents porte sur des documents fabriqués : les modèles réservés, le contrôle de réalisme et les variantes hostiles en sont le cœur, et le rapport le dit dès son résumé. Les documents réels, s'il en arrive, sont un bonus mesuré à part (décision avancée le 28 novembre 2026, voir « Modifications »).
11. Les besoins de l'utilisateur sont des hypothèses tirées de sources publiques. Elles sont listées comme telles, avec un plan pour les valider.

## 1. Besoin

### Le problème

Un client reçoit une proposition de placement (courriel, brochure, message d'un prétendu conseiller) et s'apprête à virer de l'argent. La proposition vient d'un acteur non autorisé, souvent un acteur qui imite le nom ou le site d'un établissement agréé.

Aujourd'hui, la banque exécute le virement au plus tard à la fin du jour ouvrable suivant, et n'a pas de droit général de le bloquer ; le refus d'exécution est limité aux cas prévus par la loi [1]. La Cour de cassation a jugé, le 1er octobre 2025, qu'un prestataire de paiement engage sa responsabilité s'il n'alerte pas son client quand le bénéficiaire figure sur la liste noire de l'AMF [1]. Le texte officiel de l'arrêt sera ajouté au dépôt.

Demain, le compromis européen sur les services de paiement prévoit qu'en cas de soupçon de fraude objectivement justifié, la banque du payeur suspend le virement, contacte le client et décide ; la preuve de ses diligences est à sa charge [2]. Ce texte n'est pas encore publié au Journal officiel de l'Union.

### La taille du problème

Il n'existe pas de chiffre officiel récent et fiable qui mesure, chaque année, les pertes dues aux faux placements payés par virement. Les chiffres disponibles sont des estimations, sur des périmètres différents :

- le parquet de Paris estime le préjudice des escroqueries financières en France à au moins 500 millions d'euros par an, et constate une baisse du nombre de plaintes [3] ;
- le préjudice moyen observé par l'ACPR sur les trois premiers trimestres 2024 est de 69 000 euros pour les faux livrets d'épargne ; la perte moyenne déclarée à l'AMF, tous thèmes confondus, est de 29 000 euros à fin novembre 2024 [3] ;
- selon une enquête réalisée pour l'AMF en septembre 2024 auprès de 5 001 personnes, 3,2 % des Français seraient victimes d'escroqueries à l'investissement [3] ;
- en 2025, l'AMF et l'ACPR ont inscrit 1 351 nouveaux noms sur leurs six listes noires (9 269 noms au 31 décembre 2025) ; le rapport du Pôle commun ajoute : « Près de 891 cas d’usurpation d’identité ont été recensés en 2025 » [4].

Le rapport 2025 de l'Observatoire de la sécurité des moyens de paiement exclut de son périmètre les escroqueries portant sur un produit inexistant, donc les faux placements [5]. Ses chiffres servent ici de contexte sur la fraude au virement, pas de taille du problème : 484,7 millions d'euros de fraude au virement, dont 42 % sur des virements instantanés, et 516 millions d'euros de fraude par manipulation, où le client valide lui-même l'opération [5].

### L'utilisateur

L'utilisateur visé est l'analyste fraude virement d'une banque. Quand la banque suspend un virement, elle doit contacter le client et décider [2] ; on suppose que ce travail revient à ses équipes de lutte contre la fraude. Les volumes, les outils et les besoins précis de ce métier ne sont pas décrits par une source publique fiable ; ils restent des hypothèses (section 9).

### Les moments d'usage

- À l'ajout d'un nouveau bénéficiaire, ou à un montant inhabituel vers un bénéficiaire récent : niveau 1. Les récits publics de victimes montrent un premier versement petit, parfois par carte, puis des virements croissants [6][7] ; le premier versement échappe donc souvent au niveau 1, et le déclencheur sur montant inhabituel vise les suivants.
- Pendant la suspension prévue par le futur règlement, ou quand le niveau 1 alerte : niveau 2, sur le document que le client a reçu.

## 2. Recentrage : le niveau 2 est le cœur

Le niveau 2 lit le document que le client a reçu, extrait l'entité qui le sollicite (nom, domaine, adresse de courriel, numéro d'agrément cité) et vérifie cette entité par du code : listes noires, registres des acteurs autorisés, ressemblance avec un acteur agréé, âge du domaine. Il produit une fiche de constats datés et sourcés ; l'analyste décide.

Le niveau 1 ne voit que le nom du bénéficiaire saisi, le résultat de la vérification du bénéficiaire et l'historique du compte. Il ne voit pas le document. Il est utile quand le bénéficiaire porte le nom de l'entité inscrite ou d'un clone, et aveugle dans deux cas fréquents :

- l'argent part vers le compte d'un tiers ;
- l'argent part vers le propre compte du client chez un prestataire réellement autorisé. L'AMF décrit des escrocs qui proposent à la victime « de convertir son argent auprès d'un PSCA autorisé avant de l'orienter vers une plateforme de trading frauduleuse » [8]. Le virement paraît alors sain ; seul le document révèle la plateforme.

Ce cas entre dans l'évaluation tel que l'AMF le décrit. Le détail « compte au nom de la victime » n'est pas écrit par l'AMF et reste une hypothèse.

## 3. Positionnement

Depuis le 30 avril 2026, la Banque de France tient un fichier national des comptes signalés pour risque de fraude, sur la base de l'article L521-6-1 du code monétaire et financier : les prestataires de paiement y partagent les identifiants de comptes (IBAN) liés à des fraudes suspectées ou avérées [9]. Ce fichier ne connaît que les IBAN déjà signalés, et son accès est réservé aux prestataires de paiement ; il est simulé dans le projet.

L'apport de l'outil n'est donc pas la vérification des IBAN, mais les entités et marques qui sollicitent le client, pas encore reliées à un IBAN signalé.

## 4. Périmètre et versions

### v1, livrée au plus tard le 31 janvier 2027

- Niveau 1 sans modèle de langage, en moins d'une seconde : nom du bénéficiaire contre les listes et les registres, ressemblance avec un acteur agréé, résultat de la vérification du bénéficiaire, montant inhabituel vers un bénéficiaire récent.
- Niveau 2 en flux fixe : extraction par le modèle, puis vérifications par le code, détection des clones, fiche de constats.
- Documents texte seulement.
- Tests d'injection dans l'extraction dès le départ.
- Traces de chaque décision, coût et latence par analyse.
- Évaluation de la section 8 sur le test rétrospectif 2026.
- Démo publique qui rejoue des analyses enregistrées sur des acteurs fictifs, sans appel au modèle.

### v2, engagée

- Agent qui choisit ses vérifications, mesuré contre le flux fixe de la v1.
- Outils exposés par MCP, en local seulement, sans personne physique dans les réponses.
- Injections propres à l'agent : faux paramètres d'outil, tentatives d'exfiltration.
- Évaluation sur le jeu prospectif issu de la collecte quotidienne.
- Captures d'écran, avec leur propre évaluation.
- Veille des nouveaux domaines en .fr.
- Branche de données publique : question rouverte, au regard de la règle de non-republication et du risque de diffamation.

### Plus tard

Tout le reste, et en particulier : autres listes noires sous accord écrit, autres langues, intégration à un outil de gestion de cas.

## 5. Données

| Source | Usage | Conditions | Versionné |
|---|---|---|---|
| Liste noire de l'AMF sur data.gouv.fr [10] | entités inscrites, date d'inscription | Licence Ouverte 2.0 | non, téléchargée à l'exécution |
| Listes blanches de l'AMF sur data.gouv.fr [10] | sociétés de gestion (avec site internet), prestataires sur crypto-actifs | Licence Ouverte 2.0 | non |
| Registre REGAFI de l'ACPR [11] | établissements autorisés, personnes morales seulement | pas de licence ; réutilisation libre au titre des articles L321-1 et L322-1 du code des relations entre le public et l'administration, sans altération, avec la source et la date de dernière mise à jour | non |
| GLEIF | identifiants d'entités juridiques | CC0 selon GLEIF, conditions d'utilisation à lire | non |
| Liste faite à la main des domaines officiels d'une trentaine d'acteurs souvent imités | référence pour les clones | relevée sur les sites officiels, datée | oui, domaines officiels seulement |
| RDAP, par l'amorçage de l'IANA [12] | date de création du domaine | volume faible, plafonds | non |
| crt.sh [13] | premier certificat, approximation de la date de création | une requête toutes les 15 secondes | non |

Les listes de l'ACPR publiées sur ABE Infoservice ne sont pas utilisées : leur reproduction électronique est interdite sans accord préalable de l'éditeur. Le registre ORIAS n'est pas utilisé : ses conditions interdisent la réutilisation commerciale et les robots.

### Pourquoi une collecte quotidienne

Une mesure sur 40 domaines tirés au hasard dans la liste de l'AMF, faite le 27 novembre 2026, donne :

- pour les domaines inscrits en 2026, 20 tirés, dont 16 mesurables (3 extensions sans serveur RDAP, 1 domaine supprimé) : un écart médian de 183 jours entre la création du domaine et l'inscription (intervalle à 95 % de 49 à 305 jours) ; seuls 2 sur 16 étaient inscrits moins de 30 jours après leur création ;
- pour les domaines inscrits en 2022, 13 sur 20 ne répondent plus en RDAP : le domaine a été supprimé, et sa date de création est perdue.

Les domaines existent donc plusieurs mois avant leur inscription, ce qui laisse une fenêtre utile ; mais la mesure rétrospective subit un biais de survie, car les domaines supprimés disparaissent. La collecte quotidienne relève, chaque jour, un instantané de la liste de l'AMF, et pour chaque nouvelle inscription, la réponse RDAP et le premier certificat le jour même. Elle tourne sur GitHub Actions, avec des plafonds d'appels, un arrêt au premier refus de quota et un cache ; ses résultats ne sont pas publiés en v1.

### Deux jeux de documents

- Un jeu public : des documents fabriqués sur des modèles, avec des acteurs fictifs, vérifiés contre un petit registre fictif versionné dans les tests.
- Un jeu local : des documents fabriqués sur les mêmes modèles avec de vraies entrées de la liste de l'AMF, et, en bonus s'il en arrive, des documents réels reçus par des personnes qui ont donné leur accord. Les noms de personnes physiques (la personne qui a reçu le document, le prétendu conseiller) sont retirés avant l'entrée d'un document dans ce jeu, donc avant tout appel au modèle. Il n'est jamais publié ; seuls des agrégats le sont.

Le marquage « document fabriqué pour test » est retiré avant l'analyse, par une règle ou en le gardant dans les métadonnées, pour que le modèle ne le voie pas.

## 6. Cadre juridique : contraintes de conception

Cette page traduit chaque règle en contrainte sur le code. Elle n'est pas un avis juridique.

- Diffamation. L'article 29 de la loi du 29 juillet 1881 punit l'allégation d'un fait qui porte atteinte à l'honneur, « même si elle est faite sous forme dubitative » [14]. Une tournure prudente ne protège donc pas. Contrainte : la fiche n'énonce que des constats datés et sourcés (« inscrit sur la liste noire de l'AMF le JJ/MM/AAAA », « domaine créé il y a N jours, proche du domaine officiel de X ») ; jamais un qualificatif ; aucune entité réelle inscrite sur une liste noire, ni aucune entité soupçonnée, n'est nommée dans la démo publique ni dans le dépôt. Seuls les domaines officiels d'acteurs autorisés sont versionnés.
- Données d'infraction. L'article 10 du RGPD et l'article 46 de la loi du 6 janvier 1978 réservent le traitement des données relatives aux infractions à certaines catégories d'acteurs [15][16]. Contrainte : les personnes physiques sont écartées dès la lecture (dans la liste de l'AMF, environ 2 % des lignes nominatives ; dans REGAFI, les personnes physiques) ; les adresses de courriel au format prénom.nom sont écartées ; dans les documents réels, les noms de personnes physiques (la personne qui a reçu le document, le prétendu conseiller) sont retirés avant l'entrée dans le jeu local, donc avant tout appel au modèle ; les listes ne sont jamais republiées.
- Licences. Liste et listes blanches de l'AMF sous Licence Ouverte 2.0 ; REGAFI sans altération, avec la mention « Source : ACPR, registre REGAFI, données du JJ/MM/AAAA » et la date de dernière mise à jour du fichier ; les pages du site de l'AMF sont protégées : elles sont citées brièvement avec leur source, pas recopiées.
- Modèle de langage. Les conditions de l'API Gemini n'autorisent que les services payants pour une application offerte à des utilisateurs de l'Espace économique européen [17]. Contrainte : aucune clé d'API chez un hébergeur, aucun appel au modèle depuis un service ouvert au public ; la démo rejoue des analyses enregistrées. En local, l'offre gratuite sert au développement, avec des plafonds d'appels et un cache.
- Décision humaine. Le compromis européen sur les paiements n'admet une décision entièrement automatisée qu'avec des garanties [2]. Contrainte : l'outil produit une fiche de constats ; il ne bloque rien et ne décide rien.
- Règlement européen sur l'IA. D'après des commentaires et un projet de lignes directrices, les systèmes destinés à détecter la fraude financière sont exclus de la catégorie à haut risque de l'annexe III, point 5 b). Le texte officiel sera lu avant la livraison de la v1.
- Jurisprudence. L'arrêt du 1er octobre 2025 (n° 22-23.136) est cité par le rapport du HCJP [1] ; un arrêt du 18 novembre 2026 (n° 25-14.815) n'est connu que par une source secondaire non fiable. Les deux textes officiels seront ajoutés au dépôt avant d'être cités davantage.

## 7. Conception, en bref

- Le modèle extrait ; le code vérifie. La sortie du modèle suit un schéma strict ; une sortie hors schéma est rejetée et tracée.
- Le document reçu est hostile par nature : il peut contenir des instructions adressées au modèle. Le modèle ne voit aucun outil en v1 ; une injection peut au pire fausser l'extraction, ce que les tests mesurent.
- Chaque analyse laisse une trace : entrées, sortie du modèle, vérifications faites, sources et dates des données, durée, nombre de jetons.
- Le coût et la latence sont mesurés par analyse. Un scénario à 1 000 analyses par jour, puis à 10 fois plus, donne un ordre de grandeur ; c'est un scénario, pas un volume observé. Le coût dominant attendu est le temps de l'analyste, pas le modèle.

## 8. Évaluation

### Jeux et découpage dans le temps

- Mise au point : inscriptions de la liste de l'AMF jusqu'au 31 décembre 2025, et modèles de documents de mise au point.
- Test rétrospectif : inscriptions du 1er janvier 2026 jusqu'à la date de fusion de ce cadrage, et modèles de documents réservés, écrits à la main avant tout réglage. Il est sous scellés et ouvert une seule fois, pour la mesure finale de la v1. Les domaines inscrits en 2026 vus lors de la mesure de faisabilité, 20 tirés, dont 16 mesurables, en sont retirés tous les 20 ; les statistiques globales de la liste (nombre de lignes, extensions de domaine) ont été calculées sur le fichier entier et ne portent sur aucun résultat de l'outil.
- Jeu prospectif : inscriptions postérieures, issues de la collecte quotidienne. Évalué en v2.
- Usurpations annotées : environ 150 lignes de la liste de l'AMF annotées à la main avec l'acteur imité, selon des règles écrites et commitées avant l'annotation ; environ 100 en mise au point et 50 dans le test rétrospectif. Les 50 usurpations du test sont annotées sans voir aucune sortie de l'outil ni des références simples.
- Contrôle de réalisme : une vingtaine de courts extraits cités de descriptions de l'AMF, comparés aux modèles de documents.
- Documents : les seuils sont jugés sur des documents fabriqués (modèles réservés et variantes hostiles). Les documents réels, s'il en arrive, sont mesurés à part et n'entrent dans aucun seuil.

Pour mesurer ce qui n'était pas encore inscrit, la liste est reconstituée à la veille de chaque inscription, en ne gardant que les lignes inscrites avant cette date.

### Références simples

1. Recherche exacte du nom ou du domaine dans la liste du jour.
2. Recherche exacte dans la liste et dans REGAFI.
3. Correspondance approximative simple sur le nom et le domaine (distance d'édition, normalisation).
4. Extraction par expressions régulières (adresses, domaines), suivie des mêmes vérifications que l'outil.
5. Modèle seul, à qui l'on demande de juger le document, sans vérification par le code.

### Mesures et seuils

Intervalles de Wilson à 95 %. Quand aucune erreur n'est observée sur N cas, la borne haute est donnée (environ 3/N).

La colonne « Jeu public ou local » dit sur quelles données le seuil est jugé. Le jeu local repose sur des données réelles qui ne sont pas republiées ; seuls ses agrégats sont publiés. Quand un seuil porte sur les deux jeux, il doit être atteint sur chacun.

| Mesure | Effectif | Jeu public ou local | Seuil |
|---|---|---|---|
| Rappel du niveau 2 sur les usurpations pas encore inscrites (liste reconstituée la veille) | ≥ 50 usurpations annotées du test | local (lignes réelles de la liste de l'AMF) | borne basse > rappel de la meilleure référence simple sur le même jeu, et borne basse ≥ 50 % |
| Extraction correcte de l'entité qui sollicite | ≥ 100 documents des modèles réservés | les deux | borne basse ≥ 80 %, et supérieure au rappel de l'extraction par expressions régulières |
| Fausses alertes du niveau 2 | ≥ 300 acteurs autorisés (domaines officiels et personnes morales de REGAFI) | local (registres réels non republiés) | borne haute ≤ 3 % |
| Fausses alertes du niveau 1 | mêmes ≥ 300 acteurs, par leur nom | local | au plus une fausse alerte sur 300 (borne haute 1,9 %) |
| Injections qui changent l'entité extraite ou font disparaître une alerte | ≥ 100 documents injectés | les deux | borne haute ≤ 5,5 % (au plus une réussite sur 100) |
| Rappel du niveau 1 | cas fabriqués, par schéma : bénéficiaire au nom de l'entité, compte d'un tiers, compte du client chez un prestataire autorisé | les deux | aucun seuil ; publié par schéma. Aucun rappel global n'est donné, faute de répartition réelle connue entre ces schémas |
| Latence | toutes les analyses | les deux | niveau 1 : 95e centile < 1 s ; niveau 2 : publiée |
| Coût par analyse | toutes les analyses | les deux | publié, au prix payant de référence, comme scénario |

Le budget de fausses alertes est jugé sur la borne haute, le rappel sur la borne basse. Un seuil manqué est rapporté tel quel.

### Temps d'analyste

Deux groupes de 10 documents différents, tirés au hasard et de difficulté comparable : la même personne vérifie l'entité à la main (listes, registres, âge du domaine) sur le premier groupe, avec la fiche sur le second. Cette personne a construit l'outil, ce qui favorise la fiche ; le temps médian gagné est donc publié comme une indication, pas comme une mesure auprès d'utilisateurs.

## 9. Hypothèses sur l'utilisateur et plan pour les valider

Hypothèses sur l'utilisateur, tirées de sources publiques, à valider par des conversations avec des professionnels de la fraude :

- le nombre de dossiers traités par analyste et par jour ;
- le temps passé par dossier ;
- la part de fausses alertes acceptable ;
- la part des dossiers où le client peut fournir le document reçu ;
- les outils déjà consultés pour vérifier une entité ;
- l'utilité d'une fiche de constats datés et sourcés.

Plan :

- trois questions, posées lors d'une conversation avec un professionnel de la fraude bancaire, sans nom ni employeur, et seulement avec son accord : comment un dossier de faux placement est traité aujourd'hui ; quelles vérifications sont faites sur l'entité ; ce qu'une fiche devrait contenir pour faire gagner du temps ;
- si l'occasion se présente, dans un établissement bancaire et avec son accord, un test de la fiche sur 10 cas réels.

Les notes brutes restent en local. Le dépôt n'en publie que la synthèse.

## 10. Dix questions sur l'opportunité

Grille d'évaluation d'une opportunité produit [18].

1. Quel problème ? Un client vire vers un faux placement que la banque n'a pas les moyens de reconnaître au moment du virement.
2. Pour qui ? L'analyste fraude virement d'une banque.
3. Quelle taille ? Au moins 500 millions d'euros par an d'escroqueries financières selon le parquet de Paris, sans chiffre fiable propre aux faux placements payés par virement.
4. Quelles alternatives ? Les listes et le questionnaire de l'AMF pour le grand public, les outils de notation des banques, le fichier national des comptes signalés, la surveillance de marques des sociétés spécialisées. Aucune ne lit le document reçu par le client au moment du virement.
5. Pourquoi ce projet ? Une vérification par le code, datée et sourcée, sur des données publiques, avec un modèle cantonné à l'extraction.
6. Pourquoi maintenant ? Le devoir d'alerte posé par la jurisprudence, la suspension prévue par le futur règlement européen, et le fichier national des comptes signalés qui laisse de côté les entités pas encore reliées à un IBAN.
7. Comment le mettre entre les mains des utilisateurs ? En v1, une démo publique sur acteurs fictifs et un rapport ; un usage réel supposerait une intégration à l'outil de gestion de cas d'une banque, hors périmètre.
8. Comment mesurer le succès ? Par les seuils de la section 8.
9. Qu'est-ce qui est critique ? La qualité de l'extraction sur des documents hostiles, le taux de fausses alertes, et le respect des contraintes juridiques.
10. Recommandation : continuer, sous les critères d'arrêt de la section 12.

## 11. Prémortem

On suppose que le projet a échoué le 31 janvier 2027. Causes probables, et parade prévue :

- Pas de documents réels : la décision est prise dès le 28 novembre 2026 ; l'évaluation repose sur des documents fabriqués, et le rapport le dit franchement.
- Documents fictifs trop faciles, que l'outil réussit sans difficulté : modèles réservés écrits à la main, contrôle de réalisme sur les descriptions de l'AMF, variantes hostiles.
- Le niveau 1 rate la plupart des cas : c'est attendu ; il est présenté comme un filtre, et son rappel est publié par schéma.
- La correspondance approximative simple fait aussi bien que l'outil sur les clones : le résultat est publié, et l'apport est recentré sur l'extraction depuis le document (critère 3).
- Une injection fausse l'extraction : mesure par variante, et correction avant livraison si le seuil est manqué.
- Une phrase de la fiche ou de la démo vise une entité réelle : constats seulement, acteurs fictifs dans la démo, relecture de chaque texte publié.
- Une source change de format ou d'accès (liste de l'AMF, REGAFI, crt.sh) : la collecte s'arrête, le changement est documenté (critère 4).
- Les quotas gratuits du modèle baissent : cache des réponses, plafonds, jeu de test dimensionné pour tenir dans le quota (critère 5).
- Le périmètre grossit et la date du 31 janvier passe : tout ajout va en v2.

## 12. Critères d'arrêt ou de pivot

1. Décision avancée le 28 novembre 2026, avant toute mesure : l'évaluation porte sur des documents fabriqués, et le rapport le dit dès son résumé. Le 18 décembre 2026, les documents réels exploitables réunis (texte, entité qui sollicite identifiable, accord de la personne qui l'a reçu), s'il y en a, forment un bonus mesuré à part ; aucun seuil n'en dépend.
2. Le 10 janvier 2027, sur la mise au point : si l'extraction par le modèle ne dépasse pas l'extraction par expressions régulières → la v1 garde les expressions régulières, et le modèle passe en v2 sur les documents où il apporte quelque chose.
3. À la mesure finale : si la borne basse du rappel sur les usurpations pas encore inscrites ne dépasse pas la meilleure référence simple → l'outil est présenté comme une vérification datée et sourcée, sans prétendre détecter les clones mieux qu'une correspondance simple.
4. À tout moment : si une source passe sous conditions incompatibles (clé payante, interdiction de réutilisation) → arrêt de son usage, documenté, et remplacement ou retrait de la vérification correspondante.
5. À tout moment : si l'offre gratuite du modèle ne permet plus de faire tourner le test sans dépense → réduction du jeu de test avant toute mesure, ou extraction par expressions régulières seule. Aucune dépense n'est engagée.
6. Le 31 janvier 2027 : ce qui n'est pas prêt passe en v2 ; la v1 est livrée avec ce qui est mesuré.

## Sources

[1] Haut Comité juridique de la place financière de Paris, rapport du 28 janvier 2026, https://www.banque-france.fr/system/files/2026-02/Rapport_73_F.pdf

[2] Accord provisoire sur le règlement relatif aux services de paiement, document PE787.675 du 5 mai 2026, article 65 et considérants 86 e et 86 f, https://www.europarl.europa.eu/RegData/commissions/econ/inag/2026/05-05/ECON_AG(2026)787675_EN.pdf

[3] AMF, ACPR, parquet de Paris et DGCCRF, communiqué du 19 décembre 2024, https://www.amf-france.org/fr/actualites-publications/communiques/communiques-de-lamf/arnaques-financieres-les-autorites-mobilisees-dans-la-lutte-contre-ce-phenomene-massif-qui-piege-de

[4] Pôle commun ACPR-AMF, rapport annuel 2025, p. 9, https://acpr.banque-france.fr/system/files/2026-06/20260624_Rapport_annuel_2025_P%C3%B4le_commun_ACPR-AMF.pdf

[5] Observatoire de la sécurité des moyens de paiement, rapport 2025, https://www.banque-france.fr/fr/publications-et-statistiques/publications/rapport-de-lobservatoire-de-la-securite-des-moyens-de-paiement-2025

[6] MoneyVox, récits de victimes publiés en 2024 à partir d'un document de l'AMF, https://www.moneyvox.fr/votre-argent/actualites/101271/je-ressens-de-la-trahison-de-la-culpabilite-victimes-arnaques-ils-ont-perdu-des-centaines-euros

[7] InfOccitanie, 13 novembre 2026, https://infoccitanie.fr/tarn-et-garonne-arnaque-aux-faux-placements-une-femme-depouillee-de-160-000-euro/

[8] AMF, « Crypto-monnaies (bitcoin, etc.) : attention aux arnaques », page datée du 27 juillet 2026, https://www.amf-france.org/fr/espace-epargnants/proteger-son-epargne/crypto-actifs-bitcoin-etc/crypto-monnaies-bitcoin-etc-attention-aux-arnaques

[9] Banque de France, conditions générales d'utilisation du fichier national des comptes signalés pour risque de fraude, 30 avril 2026, https://www.banque-france.fr/system/files/2026-05/CGU_FNC-RF_30_avril_2026_Demarrage.pdf

[10] AMF, jeux de données sur data.gouv.fr (listes noires, sociétés de gestion de portefeuille, prestataires de services sur crypto-actifs), Licence Ouverte 2.0.

[11] ACPR, registre REGAFI, https://www.regafi.fr ; code des relations entre le public et l'administration, articles L321-1 et L322-1, Légifrance.

[12] IANA, fichier d'amorçage RDAP, https://data.iana.org/rdap/dns.json

[13] crt.sh, journal public des certificats, https://crt.sh

[14] Loi du 29 juillet 1881 sur la liberté de la presse, article 29, Légifrance, LEGIARTI000006419790.

[15] Règlement (UE) 2016/679, article 10.

[16] Loi n° 78-17 du 6 janvier 1978, article 46, Légifrance, LEGIARTI000037823133 ; CNIL, recommandations du 12 juin 2024 sur la réutilisation des données publiquement accessibles.

[17] Google, conditions supplémentaires de l'API Gemini, en vigueur le 23 mars 2026, https://ai.google.dev/gemini-api/terms

[18] M. Cagan, « Assessing Product Opportunities », Silicon Valley Product Group, 13 décembre 2006, https://www.svpg.com/assessing-product-opportunities/ (grille des dix questions de la section 10).
