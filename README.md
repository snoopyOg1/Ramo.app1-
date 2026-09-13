# RAMO — Étape 1 : connexion Airtable

Première brique du parcours RAMO (5 étapes prévues : Audit guidé → Diagnostic →
Plan de solution → Guide d'installation → Suivi avant/après). Cette étape se
limite volontairement à une connexion Airtable simple :

- une liste déroulante pour choisir une agence parmi celles déjà qualifiées
  dans Airtable ;
- l'affichage de ses infos de base : nom, ville, score prospect.

Aucune donnée n'est dupliquée : l'app lit en direct la base Airtable existante
(`Suivi Prospects Agences` → table `Agences immobilières`).

## Prérequis

- Node.js 18+
- Un Personal Access Token Airtable ayant :
  - le scope `data.records:read`
  - l'accès à la base `Suivi Prospects Agences` (`appsCrRJjuTmuw9Y3`)

Créez un token ici : https://airtable.com/create/tokens

## Installation

```bash
npm install
cp .env.local.example .env.local
# éditez .env.local et renseignez AIRTABLE_TOKEN
npm run dev
```

Ouvrez http://localhost:3000 — la liste déroulante doit se remplir avec les
agences de la base, et sélectionner une agence affiche nom / ville / score.

## Architecture (volontairement minimale)

- `pages/api/agencies.js` — route serveur Next.js qui appelle l'API Airtable
  avec le token (jamais exposé au navigateur), pagine sur toutes les
  agences et renvoie `{ id, name, city, score }`.
- `pages/index.js` — page unique : select + carte d'affichage.

Le `AIRTABLE_BASE_ID` et `AIRTABLE_TABLE_ID` sont déjà pré-remplis dans
`.env.local.example` avec les valeurs de votre base ; changez-les seulement
si vous voulez pointer vers une autre base/table.
