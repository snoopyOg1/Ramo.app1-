# RAMO — Étapes 1 à 5

Parcours RAMO (5 étapes prévues : Audit guidé → Diagnostic → Plan de
solution → Guide d'installation → Suivi avant/après). On construit un
morceau à la fois, testé avant de passer au suivant (voir `CLAUDE.md`).

## Étape 1 — connexion Airtable ✅ validée en production

- une liste déroulante pour choisir une agence parmi celles déjà qualifiées
  dans Airtable ;
- l'affichage de ses infos de base : nom, ville, score prospect.

Aucune donnée n'est dupliquée : l'app lit en direct la base Airtable existante
(`Suivi Prospects Agences` → table `Agences immobilières`).

## Étape 2 — audit guidé ✅ validée en production

À partir de l'agence sélectionnée, un questionnaire structuré en 4
sections (repris des dimensions déjà utilisées dans la table Airtable
`Opportunites`) :

- Présence digitale
- Suivi des leads & CRM
- Relances
- Taille & activité

Chaque réponse porte un statut **Fait confirmé** / **Hypothèse à
vérifier** — la même discipline que le champ `Hypotheses a verifier en
appel` de la table `Opportunites`. Pas de logique de diagnostic, pas
d'écriture dans Airtable : les réponses restent en mémoire de session.

## Étape 3 — diagnostic ✅ validée en production

Reformule les réponses de l'audit en une liste de **problèmes
identifiés**, uniquement quand la réponse donnée indique effectivement
un problème (ex. « site web non à jour », « aucun CRM en place »). Une
réponse saine (« Oui », « Oui, actifs »…) n'apparaît pas comme problème.
Chaque problème hérite du statut fait confirmé / hypothèse à vérifier de
la réponse correspondante — aucune nouvelle information n'est déduite ou
inventée. Les réponses contextuelles (outil utilisé, nombre d'agents,
volume de leads, notes libres) sont affichées à part, non classées comme
problèmes. Pas de score, pas de priorisation.

## Étape 4 — plan de solution priorisé ✅ validée en production

Pour chaque problème du diagnostic, propose une automatisation avec
**Impact**, **Complexité** et **Priorité** (grille validée avec
l'utilisateur — pas de reprise d'une grille Airtable "Agent Opportunité"
qui s'est révélée non représentée dans les données réelles, voir
`CLAUDE.md`) :

- Impact et Complexité : Faible / Moyen(ne) / Élevé(e), un couple fixe par
  catégorie de problème (`PLAN_ITEMS`)
- Priorité : calculée automatiquement par une matrice impact/effort
  standard (`PRIORITY_MATRIX`), jamais saisie à la main
- Chaque ligne du plan hérite le statut fait confirmé / hypothèse à
  vérifier du problème d'origine (affiché, sans influencer la priorité)
- Trié par priorité (Haute → Moyenne → Basse)

Pas d'écriture dans Airtable à ce stade — plan entièrement dérivé de
`st.session_state`, comme le diagnostic.

## Étape 5 — suivi avant/après (construite, en attente de validation)

Pour l'agence sélectionnée : relevé d'indicateurs libres (jusqu'à 3 par
relevé, nom + valeur en texte libre — pas de liste imposée, ça dépend de
l'automatisation) à un instant donné, marqué **Avant** ou **Après**.
Affichage côte à côte des relevés existants, **sans aucun calcul** (pas
de delta, pas de %, pas de ROI), comme demandé.

**Première écriture Airtable de l'app** (tout le reste est lecture seule) :
nouvelle table `Suivi Avant/Après` (liée à `Agences immobilières`), créée
et son schéma validé explicitement avec l'utilisateur avant codage — voir
`CLAUDE.md`. Toute erreur d'écriture (token sans le scope
`data.records:write`, Airtable indisponible) affiche un message clair,
jamais un crash — testé explicitement pour ces deux cas.

Stack : **Python + Streamlit** — une seule commande pour lancer, pas de build,
pas d'écosystème npm à gérer.

## Prérequis

- Python 3.9+
- Un Personal Access Token Airtable ayant :
  - les scopes `data.records:read` **et** `data.records:write` (l'écriture
    est nécessaire depuis l'étape 5)
  - l'accès à la base `Suivi Prospects Agences` (`appsCrRJjuTmuw9Y3`)

Créez un token ici : https://airtable.com/create/tokens — si vous avez déjà
un token en lecture seule d'une étape précédente, ajoutez-lui simplement le
scope `data.records:write` dans l'interface Airtable (la valeur du token ne
change pas, rien à retoucher dans vos secrets).

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# éditez .streamlit/secrets.toml et renseignez AIRTABLE_TOKEN

streamlit run app.py
```

Le navigateur s'ouvre automatiquement. Choisissez une agence : sa fiche
(ville / score) s'affiche, suivie du formulaire d'audit guidé, puis du
diagnostic généré à partir des réponses soumises.

## Déploiement (Streamlit Community Cloud)

Déployez depuis la branche `main` (seule branche garantie stable —
les branches de travail `claude/...` peuvent être nettoyées). Dans
**App settings → Secrets**, collez :

```toml
AIRTABLE_TOKEN = "votre_token_airtable"
AIRTABLE_BASE_ID = "appsCrRJjuTmuw9Y3"
AIRTABLE_TABLE_ID = "tblGWjkwRgKkJIps6"
AIRTABLE_SUIVI_TABLE_ID = "tblPFYGMdN7xcnqgN"
```

Pour tester une branche de travail sans toucher à cette app, déployez une
app Streamlit Cloud séparée (même repo, branche différente, URL
différente) — voir l'historique de discussion du projet pour la marche à
suivre détaillée.

## Architecture (volontairement minimale)

Un seul fichier, `app.py` :

- `fetch_agencies()` — appelle l'API Airtable avec le token (jamais exposé
  au navigateur : lu depuis `st.secrets` ou une variable d'environnement),
  pagine sur toutes les agences, filtre les lignes sans nom, trie
  alphabétiquement. Résultat mis en cache 5 minutes (`st.cache_data`).
- `render_agency_picker()` / `render_agency_card()` — étape 1.
- `AUDIT_QUESTIONS` + `render_audit_form()` — étape 2 : questionnaire
  structuré, statut fait/hypothèse par question, récapitulatif en
  mémoire de session (`st.session_state`), isolé par agence.
- `PROBLEM_STATEMENTS` + `compute_diagnostic_problems()` +
  `render_diagnostic()` — étape 3 : reformule les réponses "à problème" de
  l'audit en constats, en héritant leur statut. `compute_diagnostic_problems()`
  est partagée avec l'étape 4 pour ne pas dupliquer cette logique.
- `PLAN_ITEMS` + `PRIORITY_MATRIX` + `render_plan()` — étape 4 : une
  automatisation par catégorie de problème, Impact/Complexité fixes,
  Priorité calculée (jamais saisie à la main).
- `fetch_suivi()` / `save_suivi_snapshot()` / `render_suivi()` — étape 5 :
  lit et écrit dans la table Airtable `Suivi Avant/Après`. Toute erreur
  (token sans droit d'écriture, service indisponible) est convertie en
  message clair (`st.error`), jamais un crash brut.
- `main()` — assemble le tout.

Diagnostic et plan sont purement dérivés de `st.session_state` : aucune
saisie supplémentaire, aucun appel réseau au-delà du chargement des
agences. Le suivi avant/après est la seule partie qui lit ET écrit dans
Airtable à chaque interaction (pas de cache, pour toujours afficher la
donnée fraîche juste après un enregistrement).

Le `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` et `AIRTABLE_SUIVI_TABLE_ID`
sont déjà pré-remplis dans `.streamlit/secrets.toml.example` avec les
valeurs de votre base ; changez-les seulement si vous voulez pointer vers
une autre base/table.

## Tests

Pas de framework de test lourd pour un projet de cette taille — validation
via `streamlit.testing.v1.AppTest` (exécute réellement `app.py`, simule la
sélection d'agence, le remplissage des formulaires, les soumissions et le
contenu généré à chaque étape) avec des réponses Airtable simulées —
y compris les chemins d'erreur d'écriture (token sans droit d'écriture,
service indisponible) pour l'étape 5. Fait avant chaque livraison, pas de
suite de tests committée pour l'instant vu la taille du projet.
