# RAMO — Étape 1 : connexion Airtable

Première brique du parcours RAMO (5 étapes prévues : Audit guidé → Diagnostic →
Plan de solution → Guide d'installation → Suivi avant/après). Cette étape se
limite volontairement à une connexion Airtable simple :

- une liste déroulante pour choisir une agence parmi celles déjà qualifiées
  dans Airtable ;
- l'affichage de ses infos de base : nom, ville, score prospect.

Aucune donnée n'est dupliquée : l'app lit en direct la base Airtable existante
(`Suivi Prospects Agences` → table `Agences immobilières`).

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

Le navigateur s'ouvre automatiquement — la liste déroulante doit se remplir
avec les agences de la base, et sélectionner une agence affiche nom / ville /
score.

## Architecture (volontairement minimale)

Un seul fichier, `app.py` :

- `fetch_agencies()` — appelle l'API Airtable avec le token (jamais exposé
  au navigateur : lu depuis `st.secrets` ou une variable d'environnement),
  pagine sur toutes les agences, filtre les lignes sans nom, trie
  alphabétiquement. Résultat mis en cache 5 minutes (`st.cache_data`).
- `main()` — select d'agence + affichage ville / score.

Le `AIRTABLE_BASE_ID` et `AIRTABLE_TABLE_ID` sont déjà pré-remplis dans
`.streamlit/secrets.toml.example` avec les valeurs de votre base ; changez-les
seulement si vous voulez pointer vers une autre base/table.
