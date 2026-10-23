# Plan — bibliothèque GPX centrée sur Wanderer

**Statut :** proposition à valider  
**Date :** 2026-10-23

## Objectif

Disposer d’un seul endroit pour retrouver, filtrer, éditer et versionner les parcours GPX, avec Komoot comme source et destination assistées, Wanderer comme catalogue principal, et gpx.studio comme éditeur. Il doit aussi être possible de créer un parcours entièrement nouveau dans gpx.studio et de l’ajouter à Wanderer même s’il n’a pas encore d’identifiant Komoot.

Le fichier GPX reste la donnée de référence. Une synchronisation ou un import ne doit jamais écraser silencieusement une version conservée.

## Décision d’architecture proposée

- **Wanderer devient le catalogue et l’interface principaux.** Il fournit déjà la recherche, les filtres, les cartes, l’import GPX et une API.
- **Réutiliser son plug-in Komoot**, après validation et correction de sa synchronisation. Le plug-in upstream importe déjà les deux types Komoot et les distingue : `tour_planned` devient `planned`, `tour_recorded` devient `completed`.
- **Modéliser l’historique des versions dans Wanderer** si l’équipe upstream accepte cette évolution. Sinon, maintenir un fork ciblé de Wanderer, avec une stratégie de rebase.
- **Ne pas forker gpx.studio pour le lire ou l’ouvrir.** Il est déjà auto-hébergé sous notre contrôle. Toutefois, son code tourne dans le navigateur et conserve ses fichiers dans IndexedDB local au navigateur ; le serveur qui héberge les fichiers statiques ne possède pas ces données. Pour enregistrer un résultat dans Wanderer, la solution propre est une action explicite côté client qui exporte le GPX courant et l’envoie à l’API Wanderer. Tester si cette petite intégration peut être proposée en amont ; sinon, une modification locale limitée de gpx.studio peut être nécessaire, sans forker tout le projet.
- **Réserver l’extension Firefox à Komoot.** Elle sert à faciliter l’envoi vers Komoot depuis Wanderer, pas à relier les données gpx.studio à Wanderer.
- **Ne pas automatiser les endpoints privés de Komoot.** L’extension doit s’appuyer sur le parcours d’import officiel et laisser une confirmation à l’utilisateur.

Cette approche évite de partir sur deux forks. Un fork Wanderer reste possible pour un véritable historique intégré, et une petite modification de gpx.studio pourrait être nécessaire pour l’enregistrement direct. Les deux décisions sont différées jusqu’aux prototypes et à la vérification des possibilités upstream.

## Modèle métier des parcours et versions

Ne pas confondre le type de parcours et la provenance d’un fichier :

| Notion | Sens | Traitement proposé |
| --- | --- | --- |
| Type `planned` | Itinéraire préparé, pas une sortie GPS réalisée | Parcours de référence modifiable et versionnable |
| Type `recorded` | Activité réellement enregistrée sur le terrain par Komoot ou un GPS | Sortie distincte ; reliée au plan correspondant seulement si confirmé |
| Provenance | Source de la version : Komoot, gpx.studio, autre import ou création manuelle | Métadonnée de version, pas un type de parcours |

Je ne recommande pas de créer un type `edited` : cela dupliquerait la distinction entre « planifié » et « enregistré ». Un GPX édité dans gpx.studio reste un parcours `planned` ; son origine (`gpx.studio`) et sa relation à la version parente indiquent qu’il s’agit d’une nouvelle version. Ainsi, on conserve l’information utile sans ajouter un état métier ambigu.

Chaque version devrait au minimum porter : identifiant interne du parcours logique, type (`planned` ou `recorded`), provenance, fichier GPX immuable, date d’import, empreinte de contenu, parent éventuel et note facultative. L’identifiant Komoot est une référence externe facultative, pas la clé de notre modèle : un itinéraire créé dans gpx.studio peut donc être ajouté immédiatement à Wanderer avec son propre identifiant interne, sans Komoot ID. Une sync identique est idempotente ; un GPX Komoot modifié crée une nouvelle version ; une activité enregistrée n’écrase jamais un plan.

**Clarification des activités enregistrées :** un *summit log* Wanderer est une entrée de sortie réellement effectuée, attachée à une page de parcours de référence. Komoot fournit peut-être déjà une relation entre un itinéraire de la bibliothèque et une activité enregistrée ensuite ; il faut la vérifier sur les données réellement exportées/importées, sans supposer qu’elle existe ni qu’elle est conservée par le plug-in. Si cette relation est disponible, l’utiliser comme indice fort. Sinon, et même en complément, Wanderer doit pouvoir suggérer des parcours planifiés similaires à partir de la géométrie GPX et présenter un indice de concordance ainsi que les raisons principales du score. L’utilisateur confirme ou rejette la relation ; sans confirmation, l’activité reste autonome. Le score ne doit pas déclencher seul un rattachement automatique au départ.

## Plan d’exécution

### Phase 0 — Vérifier et sauvegarder

1. Sauvegarder `komoot-library/tours/` et les métadonnées avant toute migration.
2. Constituer un jeu d’essai connu : un itinéraire planifié, une activité enregistrée, un plan modifié depuis le dernier import, et un fichier édité dans gpx.studio.
3. Rejouer l’import Komoot dans Wanderer et noter, pour chacun, le type, le GPX obtenu, la création ou non d’un objet, les métadonnées et le résultat d’une seconde sync.
4. Vérifier spécifiquement si Komoot expose ou exporte un lien entre un itinéraire planifié de la bibliothèque et l’activité enregistrée en le suivant, et si le plug-in Wanderer préserve ce lien.
5. Examiner les versions exactes de Wanderer et du plug-in Komoot déployées ; le comportement observé doit être vérifié sur ces versions avant de conclure.

**Sortie attendue :** diagnostic reproductible du bug d’import et décision sur la faisabilité de l’upstream contribution ou du fork.

### Phase 1 — Corriger l’import Komoot

1. Distinguer les itinéraires planifiés (`tour_planned`) des activités enregistrées (`tour_recorded`) à chaque import.
2. Pour une référence externe déjà connue, comparer la date de modification ou l’empreinte du GPX. Ne pas ignorer un GPX réellement modifié.
3. En cas de modification du plan, enregistrer une nouvelle version et garder les anciennes.
4. Garantir l’idempotence : réimporter le même contenu ne crée ni doublon ni nouvelle version.
5. Documenter les erreurs partielles (tour listé mais GPX indisponible, authentification expirée, type inconnu) au lieu de les présenter comme un import réussi.

**Critères d’acceptation :** plan et activité correctement classés ; modification visible comme nouvelle version ; seconde sync identique sans changement ; aucune version existante supprimée.

### Phase 2 — Définir et intégrer le versionnement

1. Tester une représentation minimale avec les collections/API actuelles de Wanderer, sans changement de schéma, pour valider l’expérience et l’import des GPX.
2. Concevoir ensuite une relation explicite parcours → versions, plutôt que de détourner les tags ou d’écraser le GPX du trail.
3. Ajouter à l’interface Wanderer une liste chronologique des versions, la provenance, le type, l’aperçu, le téléchargement et la sélection de la version courante.
4. Permettre de restaurer une version planifiée comme nouvelle version, sans supprimer l’historique.
5. Permettre de créer un parcours planifié sans référence externe Komoot ; utiliser l’identifiant interne Wanderer comme identité et ajouter une référence Komoot seulement si elle existe ultérieurement.
6. Ajouter un outil de rapprochement pour les activités enregistrées : utiliser d’abord un lien explicite fourni par Komoot s’il existe, puis rechercher des parcours planifiés candidats par similarité des traces. Afficher un score de concordance et des éléments explicatifs (par exemple recouvrement spatial, distance/durée et sens ou ordre du parcours quand ils sont disponibles) ; permettre à l’utilisateur de confirmer, rejeter ou différer le lien.
7. Enregistrer les liens confirmés comme une relation explicite entre l’activité et le parcours, en gardant la méthode et la provenance du rapprochement. Un lien Komoot explicite peut être préproposé ; un rapprochement géométrique reste une suggestion jusqu’à confirmation.
8. N’envisager un rattachement automatique que plus tard, après évaluation sur des exemples confirmés et mesure des faux positifs. Le rendre désactivable et conserver une possibilité de revue/correction ; le score seul ne constitue pas une preuve.

**Critères d’acceptation du rapprochement :** les activités sans candidat fiable restent autonomes ; les candidats proposés affichent leur score et les critères compréhensibles ; seul un lien confirmé par l’utilisateur est enregistré comme certain ; un lien erroné peut être retiré ou corrigé sans modifier les GPX ni l’historique des versions.

**Décision de maintenance :** proposer d’abord ces changements à upstream Wanderer. Si le modèle ou l’interface nécessaire est refusé ou incompatible avec le calendrier, maintenir un fork limité au modèle de version, aux API et aux vues concernées. Éviter un fork général non documenté.

### Phase 3 — Enregistrer les parcours créés ou édités dans gpx.studio

1. Ouvrir une version planifiée depuis Wanderer dans gpx.studio en transmettant son GPX, sans créer de nouvelle version à la simple ouverture.
2. Ajouter une action « Enregistrer dans Wanderer » qui exporte le document GPX actuellement ouvert depuis le navigateur vers une API d’import/versionnement Wanderer. L’enregistrement demande si c’est un nouveau parcours ou une nouvelle version d’un parcours existant.
3. Pour une création sans parent, créer un nouveau parcours `planned` avec identifiant interne Wanderer et sans identifiant Komoot. Pour une édition, créer une nouvelle version avec provenance `gpx.studio` et lien vers sa version parente.
4. Garder une voie de secours par téléchargement GPX puis import manuel Wanderer.
5. Tester une intégration client-à-API authentifiée, à jeton révocable ; ne jamais placer un mot de passe Komoot ou un jeton Wanderer dans l’URL.

**Note technique :** l’application gpx.studio s’exécute dans le navigateur. Dans la révision examinée, ses fichiers et réglages sont dans IndexedDB du navigateur, et non dans un stockage du serveur. Même si Wanderer et gpx.studio partagent une origine, cela rendrait certaines données accessibles au JavaScript du navigateur sous cette origine, pas au serveur Wanderer. Éviter de coupler Wanderer au schéma IndexedDB privé de gpx.studio ; utiliser un export GPX explicite et une API stable. L’ouverture d’un GPX via URL existe déjà ; l’enregistrement vers Wanderer est le point à développer.

**Critères d’acceptation :** l’ouverture seule ne modifie pas la bibliothèque ; une création gpx.studio devient un nouveau parcours planifié sans Komoot ID ; une édition crée une version liée au parent ; les versions antérieures restent intactes ; le GPX peut être rouvert et téléchargé.

### Phase 4 — Simplifier le retour vers Komoot avec Firefox

1. Depuis un parcours planifié dans Wanderer, l’utilisateur déclenche l’extension ; celle-ci récupère ou télécharge le GPX courant et lui donne un nom clair.
2. L’extension ouvre l’écran officiel d’import Komoot. Si Firefox ou Komoot ne permet pas de transmettre directement le fichier au sélecteur, l’utilisateur choisit le GPX qui vient d’être préparé.
3. Évaluer les permissions Firefox et le parcours réel d’import ; ne pas présumer que l’extension peut remplir le sélecteur de fichiers ni contourner une confirmation.
4. N’utiliser aucun endpoint privé pour automatiser l’envoi. Garder une validation explicite par l’utilisateur ; après confirmation, proposer d’associer la référence Komoot au parcours Wanderer existant si elle peut être obtenue de manière fiable.

**Critères d’acceptation :** le parcours choisi dans Wanderer est celui préparé pour l’import ; l’utilisateur confirme l’envoi dans l’interface Komoot ; aucun succès n’est annoncé avant confirmation ; la référence Komoot peut être liée au parcours interne existant sans créer un doublon.

### Phase 5 — Migrer puis retirer le catalogue provisoire

1. Importer les GPX et métadonnées existants sans perte, en rapprochant par ID Komoot et en signalant les ambiguïtés.
2. Vérifier les comptes de fichiers, les empreintes, les catégories, les parcours sans ID et les doublons potentiels.
3. Exécuter une période de comparaison où le catalogue actuel reste disponible en lecture seule.
4. Après validation seulement, basculer l’usage vers Wanderer et archiver ou retirer l’ancien catalogue. Garder une sauvegarde restaurable.

## Rôle `komoot_export` dans la bibliothèque actuelle

`komoot_export` n’est pas un type Komoot. Dans `scripts/komoot_library.py`, ce rôle est attribué lorsque la commande utilise `--tour-type all`. Cette option range ensemble les GPX planifiés et enregistrés sous `01_komoot_sync.gpx` ; elle perd donc la distinction attendue.

Ne pas convertir automatiquement tous les fichiers portant ce rôle en `planned`. Les reclasser à partir d’une source fiable (type Komoot vérifié, GPX source ou nouvel import séparé). Les entrées qui ne peuvent pas être identifiées restent `unknown`/« à vérifier » jusqu’à confirmation.

## Upload vers Komoot : limites et options

L’import GPX par l’interface Komoot est documenté ; je n’ai pas identifié d’API publique documentée pour téléverser un itinéraire. Le plug-in Komoot de Wanderer vérifié ici est un importeur Komoot → Wanderer et ne déclare pas d’envoi vers Komoot.

La piste d’une extension Firefox est raisonnable pour réduire les étapes manuelles, mais ne garantit pas un téléversement invisible : une extension ne peut pas supposer qu’elle a le droit de remplir un sélecteur de fichiers ou de contourner les confirmations du site. Le résultat visé est d’abord un assistant du flux officiel, avec une étape de validation par l’utilisateur. Une automatisation intégrale ne sera considérée que si Komoot propose une interface supportée pour cela.

## Risques et points à trancher après le prototype

- Le plug-in Wanderer peut ignorer les références Komoot déjà importées, même si leur GPX a évolué ; le test de la phase 0 doit confirmer ce comportement pour la version déployée.
- Les sorties Komoot peuvent être liées ou non à un plan Wanderer ; demander une confirmation lorsqu’aucun identifiant ou lien explicite ne permet le rapprochement.
- La qualité d’un score de similarité dépend des traces disponibles et du choix des seuils ; mesurer les faux positifs avant d’automatiser un lien.
- Les données de gpx.studio sont stockées côté navigateur ; l’auto-hébergement de son frontend ne les centralise pas sur le serveur.
- Un fork Wanderer implique de suivre l’upstream et de gérer les migrations de données ; ouvrir une proposition upstream avant de figer le fork.
- L’extension Firefox peut être limitée par les permissions d’accès aux fichiers et les changements de l’interface Komoot ; prévoir un flux manuel de secours.
- Komoot s’appuie sur des interfaces et comportements susceptibles de changer ; ne pas considérer ses endpoints privés comme un contrat stable.

## Sources examinées

- [Plug-in Komoot de Wanderer](https://github.com/open-wanderer/wanderer/tree/dev/plugins/komoot) : types planifié/enregistré, mapping et synchronisation.
- [API Wanderer](https://wanderer.to/develop/api) : import et mise à jour des trails.
- [Import/export Wanderer](https://wanderer.to/use/import-export/) : API et dossier d’auto-import.
- Code gpx.studio examiné : `website/src/lib/db.ts` (Dexie/IndexedDB) et `website/src/routes/[[language]]/app/+page.svelte` (chargement des GPX transmis par URL).
- [Documentation Komoot sur les fichiers GPS](https://support.komoot.com/hc/en-us/articles/360022834132-Export-and-import-GPS-files) : import depuis l’interface.
- Code local : `scripts/komoot_library.py`, `komoot-library/tours/<id>/meta.json`.

## Exigences et traçabilité

| Exigence | Plan |
| --- | --- |
| Import Komoot utilisable depuis l’interface et vérifié | Phases 0–1 |
| Importer des parcours planifiés et des activités enregistrées sous des types distincts | Phases 0–1 ; rôle `komoot_export` |
| Enregistrer un parcours créé dans gpx.studio dans Wanderer sans Komoot ID | Phases 2–3 |
| Préserver les modifications gpx.studio comme versions planifiées avec leur provenance | Phases 2–3 |
| Distinguer les sorties enregistrées des parcours planifiés et les relier explicitement si nécessaire | Phases 1–2 |
| Proposer des liens entre activités enregistrées et parcours similaires avec score et confirmation utilisateur | Phases 0 et 2 |
| Utiliser Wanderer pour l’affichage, la recherche et les filtres | Décision d’architecture ; phases 2 et 5 |
| Évaluer un upload Komoot simplifié sans supposer une API non documentée | Phase 4 |
| Évaluer l’extension Firefox pour aider à envoyer un parcours Wanderer vers Komoot | Phase 4 |
| Éviter une dépendance à deux forks si une intégration upstream ou une modification locale ciblée suffit | Décision d’architecture ; phases 2–3 |
| Migrer les GPX existants sans perte | Phase 5 |
