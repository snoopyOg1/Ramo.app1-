# RAMO — Contexte projet pour Claude

Ce fichier documente les décisions actées pour ce projet. À lire avant toute
intervention, pour éviter de dévier de choix déjà arbitrés (voir l'épisode
Next.js du commit initial : construit sans vérifier ce fichier, qui
n'existait pas encore — corrigé ensuite en Python + Streamlit).

## Stack technique : Python + Streamlit

Décision actée, non négociable sans en discuter explicitement avec
l'utilisateur : **Python + Streamlit**, pas de framework JS (Next.js,
React, etc.).

Raison : l'utilisateur ne code pas. Streamlit permet une seule commande
pour lancer (`streamlit run app.py`), pas de build, pas d'écosystème npm
à maintenir.

- Dépendances minimales (`requirements.txt`), pas de librairie ajoutée
  sans nécessité claire.
- Un fichier `app.py` par étape tant que la taille reste raisonnable ;
  découper en modules seulement quand `app.py` devient difficile à suivre
  — pas préventivement.
- Secrets via `st.secrets` (`.streamlit/secrets.toml`, jamais commité) ou
  variable d'environnement en fallback. Jamais de clé en dur dans le code.

## Connexion aux données : Airtable existant, jamais de duplication

L'app se connecte aux bases Airtable existantes de l'utilisateur, en
lecture directe à chaque besoin (ou via cache court `st.cache_data`).
Elle ne duplique jamais les données dans une base locale, un fichier, ou
un autre store.

Base connue à ce jour :
- **Suivi Prospects Agences** — base ID `appsCrRJjuTmuw9Y3`
  - table `Agences immobilières` (ID `tblGWjkwRgKkJIps6`) : 133
    agences immobilières qualifiées (champs clés : `nom de l'agence`,
    `ville`, `score prospect`, `statut`, etc.)
  - table `Opportunites` (ID `tblf2020OCEiZsxOu`) : liée à la table
    agences, détail de scoring (`Score total`, `Statut opportunite`,
    etc.) — **"Opportunités" est une table dans cette base, pas une
    base séparée**, malgré la mention initiale de deux bases distinctes.

Avant de coder contre une base/table Airtable, vérifier son schéma exact
via le connecteur Airtable MCP disponible dans Claude Code plutôt que de
supposer les noms de champs.

## Périmètre V1 : 5 étapes du parcours

1. **Audit guidé**
2. **Diagnostic** — distinction stricte fait confirmé / hypothèse à
   vérifier (ne jamais présenter une hypothèse comme un fait)
3. **Plan de solution priorisé**
4. **Guide d'installation pas à pas**
5. **Suivi avant/après**

## Méthode incrémentale

On construit **un morceau à la fois**, testé avant de passer au suivant.
Ne jamais anticiper ou construire une étape suivante sans validation
explicite de l'étape en cours par l'utilisateur.

État actuel : **Étape 1 uniquement** — connexion Airtable, sélection
d'une agence dans une liste déroulante, affichage nom / ville / score.
Rien au-delà tant que ce n'est pas validé.

## Sécurité

- Aucun token/clé API en dur dans le code ou committé (voir
  `.gitignore` : `.streamlit/secrets.toml`, `.env`).
- Le token Airtable n'est utilisé que côté serveur (process Streamlit),
  jamais exposé au client/navigateur.
- Toute dépendance ajoutée doit être vérifiée sans vulnérabilité connue
  avant d'être committée (`pip install` + vérification, pas d'ajout
  "par défaut" sans contrôle).
- Avant de dévier d'une décision listée dans ce fichier (stack, méthode,
  périmètre), le signaler explicitement à l'utilisateur et demander
  confirmation plutôt que de trancher seul.
