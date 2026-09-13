# RAMO — Étapes 1, 2 & 3

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

## Étape 3 — diagnostic (construite, en attente de validation)

Reformule les réponses de l'audit en une liste de **problèmes
identifiés**, uniquement quand la réponse donnée indique effectivement
un problème (ex. « site web non à jour », « aucun CRM en place »). Une
réponse saine (« Oui », « Oui, actifs »…) n'apparaît pas comme problème.
Chaque problème hérite du statut fait confirmé / hypothèse à vérifier de
la réponse correspondante — aucune nouvelle information n'est déduite ou
inventée. Les réponses contextuelles (outil utilisé, nombre d'agents,
volume de leads, notes libres) sont affichées à part, non classées comme
problèmes. Pas de score, pas de priorisation (ça viendra à l'étape 4).

Stack : **Python + Streamlit** — une seule commande pour lancer, pas de build,
pas d'écosystème npm à gérer.

## Prérequis

- Python 3.9+
- Un Personal Access Token Airtable ayant :
  - le scope `data.records:read`
  - l'accès à la base `Suivi Prospects Agences` (`appsCrRJjuTmuw9Y3`)

Créez un token ici : https://airtable.com/create/tokens

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
- `PROBLEM_STATEMENTS` + `render_diagnostic()` — étape 3 : reformule les
  réponses "à problème" de l'audit en constats, en héritant leur statut.
  Purement dérivé de `st.session_state` : aucune saisie, aucun appel
  réseau supplémentaire.
- `main()` — assemble le tout.

Le `AIRTABLE_BASE_ID` et `AIRTABLE_TABLE_ID` sont déjà pré-remplis dans
`.streamlit/secrets.toml.example` avec les valeurs de votre base ; changez-les
seulement si vous voulez pointer vers une autre base/table.

## Tests

Pas de framework de test lourd pour un projet de cette taille — validation
via `streamlit.testing.v1.AppTest` (exécute réellement `app.py`, simule la
sélection d'agence, le remplissage du formulaire, la soumission et — pour
l'étape 3 — le contenu du diagnostic généré) avec des réponses Airtable
simulées. Fait avant chaque livraison, pas de suite de tests committée
pour l'instant vu la taille du projet.
