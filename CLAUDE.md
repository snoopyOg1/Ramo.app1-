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
un autre store. Depuis l'étape 5, elle écrit aussi dans une table dédiée
(`Suivi Avant/Après`, voir ci-dessous) — la seule écriture de l'app à ce
jour, dans une table créée spécifiquement pour elle (pas de modification
de données existantes d'agences/opportunités).

Base connue à ce jour :
- **Suivi Prospects Agences** — base ID `appsCrRJjuTmuw9Y3`
  - table `Agences immobilières` (ID `tblGWjkwRgKkJIps6`) : 132-133
    agences immobilières qualifiées (champs clés : `nom de l'agence`,
    `ville`, `score prospect`, `statut`, `nombre d'agents estimé`, etc.)
  - table `Opportunites` (ID `tblf2020OCEiZsxOu`) : liée à la table
    agences, détail de scoring sur 4 dimensions (`Presence digitale`,
    `Absence de CRM`, `Taille structure`, `Activite confirmee`) plus un
    champ `Hypotheses a verifier en appel` — **"Opportunités" est une
    table dans cette base, pas une base séparée**, malgré la mention
    initiale de deux bases distinctes. Ces 4 dimensions ont servi de
    trame aux questions de l'audit guidé (étape 2).
  - table `Suivi Avant/Après` (ID `tblPFYGMdN7xcnqgN`) : créée le
    2026-09-14 pour l'étape 5. Un enregistrement = un relevé d'indicateurs
    pour une agence à un instant donné (`Agence` lien, `Date`, `Moment`
    Avant/Après, jusqu'à 3 paires `Indicateur N - nom` / `Indicateur N -
    valeur` en texte libre, `Notes`). Schéma proposé puis validé
    explicitement par l'utilisateur avant création. **Seule table de ce
    projet où l'app écrit, pas seulement lit** — le token Airtable de
    déploiement doit avoir le scope `data.records:write` en plus de
    `data.records:read`.

Avant de coder contre une base/table Airtable, vérifier son schéma exact
via le connecteur Airtable MCP disponible dans Claude Code plutôt que de
supposer les noms de champs.

### ⚠️ Incohérence documentaire connue — à corriger plus tard (pas urgent)

La base **RAMO - Fiches Agents** (`apppAOsJkmODOcBk3`, table `Fiches
Agents`) contient une fiche **"Agent Opportunité"** dont le champ Output
affirme : *"Une ou plusieurs lignes dans la table 'Opportunités' ... :
automatisation, impact, complexité, priorité, score commercial,
justification"* et un statut *"Construit et testé sur les 13 agences de
Creil (audits migrés)"*.

Vérifié le 2026-09-13 : **ce résultat n'existe pas dans les données
réelles**. Les 70 enregistrements de la table `Opportunites` (dont les
13 du lot "Creil-test-1") ne contiennent que la grille de qualification
Agent Prospect (Presence digitale, Absence de CRM, Taille structure,
Activite confirmee, Statut opportunite) — aucun champ automatisation,
impact, complexité, priorité ou score commercial. Confirmé par
l'utilisateur : l'évaluation Creil a été faite au cas par cas en
conversation, jamais formalisée dans une grille écrite quelque part.

**À faire plus tard** (pas maintenant) : corriger la fiche "Agent
Opportunité" dans RAMO - Fiches Agents pour refléter la réalité — soit
en retirant l'affirmation de résultat testé, soit en y réconciliant
la grille Impact/Complexité/Priorité effectivement utilisée dans RAMO
(étape 4, voir plus bas), une fois celle-ci stabilisée.

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

État actuel :
- **Étape 1 — validée en production.** Testée par l'utilisateur en
  conditions réelles sur Streamlit Community Cloud (132 agences
  chargées, ex. ABD Immobilier / Creil / score 81). Fusionnée dans
  `main`.
- **Étape 2 — audit guidé, validée en production.** Testée par
  l'utilisateur en conditions réelles (statuts Fait confirmé/Hypothèse
  à vérifier corrects, "Non renseigné" fonctionnel, pas de fuite d'état
  entre agences). Fusionnée dans `main` : c'est la branche à déployer.
- **Étape 3 — diagnostic, validée en production.** Testée par
  l'utilisateur en conditions réelles sur téléphone (mélange réponse
  problème / bonne réponse / réponse "Partiel" : problèmes identifiés
  corrects, statuts fait confirmé/hypothèse à vérifier bien hérités,
  réponses saines absentes de la liste). Pure reformulation des
  réponses de l'audit (pas de nouvelle information déduite) ; pas de
  score ni de priorisation ; pas d'écriture dans Airtable. Fusionnée
  dans `main` : c'est la branche à déployer.
- **Étape 4 — plan de solution priorisé, construite et testée
  localement** (`streamlit.testing.v1.AppTest` : plan vide avant audit,
  automatisations générées uniquement pour les vraies réponses-problème,
  tri par priorité correct, statuts hérités affichés, non-régression sur
  étapes 2 et 3 après refactor de `compute_diagnostic_problems`), en
  attente de validation utilisateur en conditions réelles. Grille
  Impact/Complexité par catégorie de problème + matrice de priorité
  standard, toutes deux validées explicitement par l'utilisateur avant
  codage (pas de reprise de la grille "Agent Opportunité" d'Airtable,
  qui s'est révélée non représentée dans les données réelles — voir
  section incohérence documentaire ci-dessus). Pas d'écriture dans
  Airtable. Fusionnée dans `main` : c'est la branche à déployer.
- **Étape 5 — suivi avant/après, construite et testée localement**
  (`streamlit.testing.v1.AppTest` : aucun relevé au départ, validation
  "indicateur 1 requis" sans appel Airtable si vide, enregistrement
  réussi visible après rerun, isolation entre agences, ET les 3 chemins
  d'erreur d'écriture/lecture explicitement demandés par l'utilisateur —
  token sans scope `data.records:write` (403), Airtable indisponible
  (exception réseau), échec de lecture du suivi existant — chacun avec
  message clair, jamais de crash ; non-régression complète sur les
  étapes 2 à 4), en attente de validation utilisateur en conditions
  réelles. Persistance décidée avec l'utilisateur : écriture dans une
  nouvelle table Airtable `Suivi Avant/Après` (schéma validé
  explicitement avant création — voir ci-dessus) plutôt que
  `st.session_state`, parce que cette étape doit survivre entre deux
  visites espacées de plusieurs semaines. Aucun calcul de delta/ROI
  (affichage brut Avant/Après côte à côte), comme demandé. Sur la
  branche de travail `claude/airtable-connection-v1-pbiy4w`, pas encore
  mergée dans `main`.

Rien au-delà de l'étape 5 tant qu'elle n'est pas validée — et l'étape 5
est la dernière du périmètre V1.

## Sécurité

- Aucun token/clé API en dur dans le code ou committé (voir
  `.gitignore` : `.streamlit/secrets.toml`, `.env`).
- Le token Airtable n'est utilisé que côté serveur (process Streamlit),
  jamais exposé au client/navigateur.
- Toute dépendance ajoutée doit être vérifiée sans vulnérabilité connue
  avant d'être committée (`pip install` + vérification, pas d'ajout
  "par défaut" sans contrôle).
- Toute écriture Airtable (fonctions `save_*`) doit convertir l'échec en
  message clair (`st.error`), jamais laisser un crash brut ou une
  exception non gérée remonter à l'utilisateur — voir
  `save_suivi_snapshot()` comme référence (distingue explicitement le
  cas "scope manquant" du cas "service indisponible").
- Avant de dévier d'une décision listée dans ce fichier (stack, méthode,
  périmètre), le signaler explicitement à l'utilisateur et demander
  confirmation plutôt que de trancher seul.
- Avant d'écrire dans une base Airtable de production (pas seulement en
  lire) — schéma d'une nouvelle table ou données —, demander confirmation
  explicite. Fait pour l'étape 5 (`Suivi Avant/Après`, schéma proposé
  puis validé avant création) : à refaire systématiquement pour toute
  future écriture.
