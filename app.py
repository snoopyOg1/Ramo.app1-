"""RAMO — Étape 1 : connexion Airtable (sélection d'agence).
Étape 2 : audit guidé (questionnaire structuré).
Étape 3 : diagnostic (reformulation des réponses en problèmes, sans score).
Étape 4 : plan de solution priorisé (automatisation + impact/complexité/
priorité par problème, grille validée avec l'utilisateur).
Étape 5 : suivi avant/après (relevés d'indicateurs par agence, écrits dans
la table Airtable "Suivi Avant/Après" — première et seule écriture de
l'app, confirmée explicitement par l'utilisateur avant codage).

V2 (2026-09-14) : audit enrichi de 2 sections ("Prise de RDV & visites",
"Gestion documentaire & signature électronique") et plan de solution
étendu de 5 à 7 automatisations, chacune avec un guide fixe en 3 parties
(pourquoi ça compte / comment faire / piège à éviter). Le "comment faire"
est calculé dynamiquement par agence (agency_has_named_tool) : vérifier
un outil déjà nommé dans l'audit avant de dupliquer, sinon recommander
Make + Airtable — jamais de variante au cas par cas.

Aucune donnée n'est dupliquée : on lit en direct la base Airtable existante
("Suivi Prospects Agences" -> table "Agences immobilières"). Audit,
diagnostic et plan restent en mémoire de session (aucune écriture). Seul
le suivi avant/après écrit dans Airtable, avec gestion d'erreur explicite
(token sans droit d'écriture, service indisponible) — jamais de crash
silencieux.
"""

import os
from datetime import date

import requests
import streamlit as st

FIELD_NAME = "nom de l'agence"
FIELD_CITY = "ville"
FIELD_SCORE = "score prospect"

DEFAULT_BASE_ID = "appsCrRJjuTmuw9Y3"
DEFAULT_TABLE_ID = "tblGWjkwRgKkJIps6"
DEFAULT_SUIVI_TABLE_ID = "tblPFYGMdN7xcnqgN"  # table "Suivi Avant/Après"

SUIVI_FIELD_TITRE = "Titre"
SUIVI_FIELD_AGENCE = "Agence"
SUIVI_FIELD_DATE = "Date"
SUIVI_FIELD_MOMENT = "Moment"
SUIVI_FIELD_NOTES = "Notes"
SUIVI_MOMENTS = ["Avant", "Après"]

# Questionnaire d'audit guidé — repris des 4 dimensions déjà utilisées dans
# la table Airtable "Opportunites" (Présence digitale, Absence de CRM,
# Taille structure, Activité confirmée), reformulées en questions d'appel.
AUDIT_QUESTIONS = [
    {
        "key": "site_web_a_jour",
        "section": "Présence digitale",
        "label": "Le site web de l'agence est-il à jour et fonctionnel ?",
        "type": "select",
        "options": ["Oui", "Non", "Partiellement", "Pas de site identifié"],
    },
    {
        "key": "reseaux_sociaux_actifs",
        "section": "Présence digitale",
        "label": "Les réseaux sociaux sont-ils actifs (publication de moins d'un mois) ?",
        "type": "select",
        "options": ["Oui, actifs", "Présents mais peu actifs", "Absents", "Ne sait pas"],
    },
    {
        "key": "outil_suivi_leads",
        "section": "Suivi des leads & CRM",
        "label": "Avec quel outil les leads entrants sont-ils suivis aujourd'hui ?",
        "type": "text",
        "placeholder": "ex : CRM nommé, Excel/Sheets, papier, de mémoire…",
    },
    {
        "key": "crm_structure",
        "section": "Suivi des leads & CRM",
        "label": "Y a-t-il un CRM structuré en place ?",
        "type": "select",
        "options": ["Oui, CRM structuré", "Outil basique (Excel, Sheets)", "Aucun système", "Ne sait pas"],
    },
    {
        "key": "delai_relance",
        "section": "Relances",
        "label": "Délai moyen de relance d'un lead entrant",
        "type": "select",
        "options": ["Immédiat (< 1h)", "Même jour", "2 à 3 jours", "Plus d'une semaine", "Pas de process défini"],
    },
    {
        "key": "process_relance_automatise",
        "section": "Relances",
        "label": "Existe-t-il un process de relance automatisé ou systématique ?",
        "type": "select",
        "options": ["Oui", "Non", "Partiel"],
    },
    {
        "key": "rdv_rappels",
        "section": "Prise de RDV & visites",
        "label": "Y a-t-il des rappels automatiques avant un rendez-vous ? (le no-show a un coût réel)",
        "type": "select",
        "options": ["Oui, automatiques", "Rappels manuels seulement", "Aucun rappel", "Ne sait pas"],
    },
    {
        "key": "rdv_outil",
        "section": "Prise de RDV & visites",
        "label": "Avec quel outil les rendez-vous sont-ils pris et confirmés aujourd'hui ?",
        "type": "text",
        "placeholder": "ex : agenda papier, Calendly, CRM intégré, de mémoire…",
    },
    {
        "key": "doc_gestion",
        "section": "Gestion documentaire & signature électronique",
        "label": "Comment les mandats/offres/compromis sont-ils gérés aujourd'hui ?",
        "type": "select",
        "options": [
            "Signature électronique (outil dédié)",
            "Email (PDF) sans signature électronique",
            "Entièrement papier",
            "Ne sait pas",
        ],
    },
    {
        "key": "doc_outil",
        "section": "Gestion documentaire & signature électronique",
        "label": "Quel outil (le cas échéant) est utilisé pour la gestion documentaire ou la signature électronique ?",
        "type": "text",
        "placeholder": "ex : DocuSign, Yousign, aucun, ne sait pas…",
    },
    {
        "key": "nombre_agents",
        "section": "Taille & activité",
        "label": "Nombre d'agents actifs dans l'agence",
        "type": "number",
    },
    {
        "key": "volume_leads_mensuel",
        "section": "Taille & activité",
        "label": "Volume de leads reçus par mois (estimation)",
        "type": "number",
    },
]

STATUS_OPTIONS = ["Hypothèse à vérifier", "Fait confirmé"]

# Étape 3 — Diagnostic : reformulation des réponses de l'audit guidé en
# problèmes, quand la réponse choisie indique un problème. Pas de logique
# de score ici (viendra à l'étape 4) : seules les options déjà définies
# dans AUDIT_QUESTIONS sont reformulées, rien n'est déduit au-delà de ce
# qui a été répondu. Une réponse absente de ce mapping (ex. "Oui") n'est
# tout simplement pas un problème.
PROBLEM_STATEMENTS = {
    "site_web_a_jour": {
        "Non": "Le site web de l'agence n'est pas à jour ou n'est pas fonctionnel.",
        "Partiellement": "Le site web de l'agence n'est que partiellement à jour ou fonctionnel.",
        "Pas de site identifié": "Aucun site web n'a été identifié pour l'agence.",
    },
    "reseaux_sociaux_actifs": {
        "Présents mais peu actifs": "Les réseaux sociaux de l'agence sont présents mais peu actifs.",
        "Absents": "Aucun réseau social actif n'a été identifié pour l'agence.",
        "Ne sait pas": "L'activité des réseaux sociaux de l'agence n'est pas connue.",
    },
    "crm_structure": {
        "Outil basique (Excel, Sheets)": "Le suivi des leads repose sur un outil basique (Excel/Sheets), pas un CRM structuré.",
        "Aucun système": "Aucun système de suivi des leads n'est en place.",
        "Ne sait pas": "La présence d'un CRM structuré n'est pas connue.",
    },
    "delai_relance": {
        "2 à 3 jours": "Le délai moyen de relance d'un lead entrant est de 2 à 3 jours.",
        "Plus d'une semaine": "Le délai moyen de relance d'un lead entrant dépasse une semaine.",
        "Pas de process défini": "Aucun délai de relance défini pour les leads entrants.",
    },
    "process_relance_automatise": {
        "Non": "Aucun process de relance automatisé ou systématique en place.",
        "Partiel": "Le process de relance automatisé n'est que partiel.",
    },
    "rdv_rappels": {
        "Rappels manuels seulement": "Les rappels de rendez-vous sont faits manuellement, sans automatisation.",
        "Aucun rappel": "Aucun rappel de rendez-vous en place.",
        "Ne sait pas": "La présence de rappels de rendez-vous n'est pas connue.",
    },
    "doc_gestion": {
        "Email (PDF) sans signature électronique": "Les mandats/offres/compromis sont gérés par email sans signature électronique.",
        "Entièrement papier": "Les mandats/offres/compromis sont gérés entièrement en papier.",
        "Ne sait pas": "Le mode de gestion des mandats/offres/compromis n'est pas connu.",
    },
}

# Questions de l'audit dont la réponse est contextuelle (pas un choix fermé
# problème/non-problème) : affichées telles quelles dans le diagnostic,
# sans statut fait/hypothèse ni classement en "problème".
CONTEXT_QUESTION_KEYS = [
    "outil_suivi_leads",
    "rdv_outil",
    "doc_outil",
    "nombre_agents",
    "volume_leads_mensuel",
]

# Étape 4 — Plan de solution priorisé : une automatisation par catégorie de
# problème du diagnostic, avec Impact et Complexité (grille validée avec
# l'utilisateur). La Priorité n'est jamais saisie à la main : elle est
# calculée depuis PRIORITY_MATRIX ci-dessous, pour rester cohérente et
# ne pas dupliquer un jugement déjà exprimé par Impact/Complexité.
PLAN_ITEMS = {
    "site_web_a_jour": {
        "automation": "Site synchronisé automatiquement avec les annonces (CRM/portails → site).",
        "impact": "Élevé",
        "complexite": "Élevée",
        "pourquoi": "Le site web est souvent le premier point de contact d'un prospect avec "
        "l'agence — s'il est daté ou hors service, ce prospect part voir un concurrent.",
        "piege": "Refaire un site custom sans connecter automatiquement les annonces revient "
        "à recréer le même problème de mise à jour manuelle.",
    },
    "reseaux_sociaux_actifs": {
        "automation": "Publication automatique et régulière sur les réseaux sociaux.",
        "impact": "Moyen",
        "complexite": "Faible",
        "pourquoi": "Une présence sociale active entretient la visibilité de l'agence entre "
        "deux mandats, sans dépendre uniquement des portails payants.",
        "piege": "Publier sans stratégie éditoriale claire (juste pour publier) use la "
        "présence sociale sans construire de vraie audience.",
    },
    "crm_structure": {
        "automation": "Mise en place d'un CRM avec centralisation automatique des leads.",
        "impact": "Élevé",
        "complexite": "Moyenne",
        "pourquoi": "Sans CRM structuré, chaque lead dépend de la mémoire ou de la "
        "disponibilité d'une seule personne — un lead oublié est un lead perdu.",
        "piege": "Migrer vers un nouveau CRM sans reprendre l'historique des contacts "
        "existants fait perdre le travail de suivi déjà fait.",
    },
    "delai_relance": {
        "automation": "Relance automatique immédiate des nouveaux leads (email/SMS).",
        "impact": "Élevé",
        "complexite": "Faible",
        "pourquoi": "Un prospect qui contacte une agence contacte généralement plusieurs "
        "agences en même temps — le premier à répondre a un avantage réel.",
        "piege": "Automatiser la relance sans prévenir l'agent qui doit ensuite reprendre "
        "la main transforme l'automatisation en boîte noire que personne ne suit.",
    },
    "process_relance_automatise": {
        "automation": "Mise en place ou complément d'un scénario de relance automatisé.",
        "impact": "Élevé",
        "complexite": "Faible",
        "pourquoi": "Un process de relance qui dépend de la mémoire de chacun s'arrête dès "
        "qu'un agent est absent ou débordé.",
        "piege": "Automatiser la relance sans définir clairement qui reprend la main "
        "humainement à un moment donné laisse le prospect en boucle indéfiniment.",
    },
    "rdv_rappels": {
        "automation": "Rappels de rendez-vous automatisés (SMS/email) pour réduire le no-show.",
        "impact": "Élevé",
        "complexite": "Faible",
        "pourquoi": "Un rendez-vous non confirmé la veille a un risque de no-show réel — "
        "chaque visite manquée est un créneau perdu pour l'agent.",
        "piege": "Envoyer un rappel générique sans possibilité de reprogrammer en un clic "
        "pousse le prospect à ne pas répondre plutôt qu'à confirmer.",
    },
    "doc_gestion": {
        "automation": "Mise en place d'une solution de signature électronique pour "
        "mandats/offres/compromis.",
        "impact": "Moyen",
        "complexite": "Faible",
        "pourquoi": "Un mandat ou un compromis qui attend une signature papier retarde "
        "toute la chaîne — vente, financement, déménagement du client.",
        "piege": "Déployer un outil de signature électronique sans former les agents à son "
        "usage fait revenir tout le monde au papier dès le premier blocage.",
    },
}

# "Comment faire" (partie b du guide) : règle unique appliquée à chaque
# automatisation, jamais de variante au cas par cas. Si l'agence a déjà
# nommé un outil dans l'audit (CRM ou logiciel quelconque), on vérifie
# d'abord l'intégration existante plutôt que de dupliquer un système.
# Sinon, recommandation systématique Make + Airtable — le stack que RAMO
# maîtrise et a déjà validé en interne, pas un choix arbitraire au cas
# par cas.
COMMENT_FAIRE_AVEC_OUTIL = (
    "Vérifiez d'abord l'intégration native de l'outil déjà en place, ou une passerelle "
    "API/Zapier, avant de construire quoi que ce soit en parallèle — ne jamais dupliquer "
    "un système existant."
)
COMMENT_FAIRE_SANS_OUTIL = (
    "Aucun outil structuré identifié : on recommande Make + Airtable — le stack que RAMO "
    "maîtrise et a déjà validé en interne."
)

# Matrice impact/effort standard (Impact, Complexité) -> Priorité.
PRIORITY_MATRIX = {
    ("Élevé", "Faible"): "Haute",
    ("Élevé", "Moyenne"): "Haute",
    ("Élevé", "Élevée"): "Moyenne",
    ("Moyen", "Faible"): "Moyenne",
    ("Moyen", "Moyenne"): "Moyenne",
    ("Moyen", "Élevée"): "Basse",
    ("Faible", "Faible"): "Basse",
    ("Faible", "Moyenne"): "Basse",
    ("Faible", "Élevée"): "Basse",
}
PRIORITY_ORDER = {"Haute": 0, "Moyenne": 1, "Basse": 2}
PRIORITY_BADGE = {"Haute": "🔴", "Moyenne": "🟡", "Basse": "⚪"}


def get_config(key, default=None):
    """Lit la config depuis st.secrets, sinon depuis les variables d'env."""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass  # pas de secrets.toml -> on retombe sur les variables d'env
    return os.environ.get(key, default)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_agencies(token, base_id, table_id):
    """Récupère toutes les agences (pagination Airtable incluse)."""
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "fields[]": [FIELD_NAME, FIELD_CITY, FIELD_SCORE],
        "pageSize": 100,
    }

    agencies = []
    offset = None

    while True:
        if offset:
            params["offset"] = offset
        else:
            params.pop("offset", None)

        response = requests.get(url, headers=headers, params=params, timeout=15)
        if not response.ok:
            raise RuntimeError(f"Airtable a répondu {response.status_code} — {response.text}")

        data = response.json()
        for record in data.get("records", []):
            fields = record.get("fields", {})
            name = fields.get(FIELD_NAME)
            if not name:
                continue  # on ignore les lignes sans nom d'agence (données incomplètes)

            score = fields.get(FIELD_SCORE)
            agencies.append(
                {
                    "id": record["id"],
                    "name": name,
                    "city": fields.get(FIELD_CITY),
                    "score": score if isinstance(score, (int, float)) else None,
                }
            )

        offset = data.get("offset")
        if not offset:
            break

    agencies.sort(key=lambda a: a["name"].lower())
    return agencies


def render_agency_picker(agencies):
    """Étape 1 : liste déroulante. Retourne l'agence choisie (dict) ou None."""
    names = [a["name"] for a in agencies]
    selected_name = st.selectbox(
        f"Agence ({len(agencies)} au total)",
        options=names,
        index=None,
        placeholder="— Choisir une agence —",
    )
    if not selected_name:
        return None
    return next(a for a in agencies if a["name"] == selected_name)


def render_agency_card(agency):
    st.subheader(agency["name"])
    col1, col2 = st.columns(2)
    col1.metric("Ville", agency["city"] or "Non renseignée")
    col2.metric("Score prospect", agency["score"] if agency["score"] is not None else "—")


def render_audit_form(agency):
    """Étape 2 : questionnaire d'audit guidé.

    Capture les réponses et leur statut (fait confirmé / hypothèse à
    vérifier). Aucune logique de diagnostic ni calcul de score ici — ça
    viendra à l'étape 3. Rien n'est écrit dans Airtable à ce stade, les
    réponses restent en mémoire de session (st.session_state).
    """
    st.divider()
    st.header("Audit guidé")
    st.caption(
        "Répondez au fur et à mesure de l'appel. Ne cochez « Fait confirmé » "
        "que pour une information vérifiée avec l'agence — sinon laissez "
        "« Hypothèse à vérifier »."
    )

    with st.form(key=f"audit_form_{agency['id']}"):
        answers = {}
        current_section = None
        for q in AUDIT_QUESTIONS:
            if q["section"] != current_section:
                current_section = q["section"]
                st.markdown(f"**{current_section}**")

            widget_key = f"{agency['id']}_{q['key']}"
            if q["type"] == "select":
                value = st.selectbox(
                    q["label"], options=q["options"], index=None,
                    placeholder="— Sélectionner —", key=widget_key,
                )
            elif q["type"] == "number":
                value = st.number_input(
                    q["label"], min_value=0, step=1, value=None,
                    placeholder="Non renseigné", key=widget_key,
                )
            else:
                value = st.text_input(q["label"], placeholder=q.get("placeholder", ""), key=widget_key)

            status = st.radio(
                "Statut",
                options=STATUS_OPTIONS,
                index=0,
                horizontal=True,
                key=f"{widget_key}_statut",
            )
            answers[q["key"]] = {"question": q["label"], "reponse": value, "statut": status}

        st.markdown("**Notes libres**")
        notes = st.text_area(
            "Points soulevés pendant l'appel, contexte additionnel…",
            key=f"{agency['id']}_notes_libres",
        )

        submitted = st.form_submit_button("Enregistrer l'audit")

    if submitted:
        st.session_state.setdefault("audits", {})[agency["id"]] = {
            "date": date.today().isoformat(),
            "answers": answers,
            "notes": notes,
        }
        st.success("Audit enregistré pour cette session ✅ (pas encore écrit dans Airtable à ce stade)")

    saved = st.session_state.get("audits", {}).get(agency["id"])
    if saved:
        with st.expander(f"Dernier audit enregistré ({saved['date']})", expanded=submitted):
            for a in saved["answers"].values():
                badge = "✅" if a["statut"] == "Fait confirmé" else "❓"
                reponse = a["reponse"] if a["reponse"] not in (None, "") else "Non renseigné"
                st.write(f"{badge} **{a['question']}** — {reponse} _({a['statut']})_")
            if saved["notes"]:
                st.write(f"**Notes** — {saved['notes']}")


def compute_diagnostic_problems(saved):
    """Reformule les réponses "à problème" d'un audit sauvegardé en une
    liste de problèmes ({key, section, statement, statut}). Partagé entre
    le diagnostic (étape 3) et le plan de solution (étape 4) pour ne pas
    dupliquer cette logique.
    """
    problems = []
    for q in AUDIT_QUESTIONS:
        options_map = PROBLEM_STATEMENTS.get(q["key"])
        if not options_map:
            continue
        answer = saved["answers"].get(q["key"])
        if not answer:
            continue
        statement = options_map.get(answer["reponse"])
        if not statement:
            continue  # réponse donnée, mais pas une réponse "à problème"
        problems.append(
            {"key": q["key"], "section": q["section"], "statement": statement, "statut": answer["statut"]}
        )
    return problems


def render_diagnostic(agency):
    """Étape 3 : diagnostic — liste des problèmes identifiés à partir des
    réponses de l'audit guidé (étape 2). Pure reformulation : chaque
    problème hérite du statut fait confirmé / hypothèse à vérifier de la
    réponse correspondante, rien n'est recalculé ni pondéré (ça viendra à
    l'étape 4, avec le plan de solution).
    """
    st.divider()
    st.header("Diagnostic")

    saved = st.session_state.get("audits", {}).get(agency["id"])
    if not saved:
        st.info("Complétez d'abord l'audit guidé ci-dessus pour générer le diagnostic de cette agence.")
        return

    st.caption(f"Basé sur l'audit du {saved['date']}.")

    problems = compute_diagnostic_problems(saved)
    problems_by_section = {}
    for p in problems:
        problems_by_section.setdefault(p["section"], []).append(p)

    if not problems:
        st.success("Aucun problème identifié à partir des réponses de l'audit.")
    else:
        st.write(f"**{len(problems)} problème(s) identifié(s)**")
        for section, probs in problems_by_section.items():
            st.markdown(f"**{section}**")
            for p in probs:
                badge = "✅" if p["statut"] == "Fait confirmé" else "❓"
                st.write(f"{badge} {p['statement']} _({p['statut']})_")

    context_items = []
    for key in CONTEXT_QUESTION_KEYS:
        answer = saved["answers"].get(key)
        if answer and answer["reponse"] not in (None, ""):
            context_items.append(f"**{answer['question']}** — {answer['reponse']}")
    if saved.get("notes"):
        context_items.append(f"**Notes de l'audit** — {saved['notes']}")

    if context_items:
        with st.expander("Informations complémentaires (non classées comme problèmes)"):
            for item in context_items:
                st.write(item)


def agency_has_named_tool(saved):
    """Vrai si l'agence a déjà nommé un outil structuré dans l'audit (CRM
    ou logiciel quelconque) : sert à choisir entre les deux variantes
    fixes du "Comment faire" (b) du plan de solution — vérifier une
    intégration existante, ou recommander Make + Airtable par défaut.
    """
    answers = saved["answers"]
    crm = answers.get("crm_structure")
    if crm and crm["reponse"] in ("Oui, CRM structuré", "Outil basique (Excel, Sheets)"):
        return True
    for key in ("outil_suivi_leads", "rdv_outil", "doc_outil"):
        a = answers.get(key)
        if a and a["reponse"] and a["reponse"].strip():
            return True
    return False


def render_plan(agency):
    """Étape 4 : plan de solution priorisé. Pour chaque problème du
    diagnostic (étape 3), propose l'automatisation associée (PLAN_ITEMS)
    avec Impact / Complexité, une Priorité calculée par PRIORITY_MATRIX
    (grille validée avec l'utilisateur), et un guide en 3 parties fixes,
    toujours dans le même ordre :
      (a) Pourquoi ça compte — texte fixe par automatisation, jamais de
          chiffre inventé
      (b) Comment faire — règle unique calculée dynamiquement (voir
          agency_has_named_tool) : vérifier un outil déjà nommé dans
          l'audit, sinon recommander Make + Airtable
      (c) Piège classique à éviter — texte fixe par automatisation
    Le statut fait confirmé / hypothèse à vérifier est hérité du problème
    d'origine, affiché mais n'influence pas la priorité. Rien écrit dans
    Airtable : plan entièrement dérivé de st.session_state, comme le
    diagnostic.
    """
    st.divider()
    st.header("Plan de solution priorisé")

    saved = st.session_state.get("audits", {}).get(agency["id"])
    if not saved:
        st.info("Complétez d'abord l'audit guidé ci-dessus pour générer le plan de cette agence.")
        return

    problems = compute_diagnostic_problems(saved)
    if not problems:
        st.success("Aucun problème identifié : pas de plan à proposer pour le moment.")
        return

    comment_faire = COMMENT_FAIRE_AVEC_OUTIL if agency_has_named_tool(saved) else COMMENT_FAIRE_SANS_OUTIL

    plan_rows = []
    for p in problems:
        item = PLAN_ITEMS.get(p["key"])
        if not item:
            continue  # pas d'automatisation définie pour cette catégorie
        priorite = PRIORITY_MATRIX[(item["impact"], item["complexite"])]
        plan_rows.append(
            {
                "problem": p["statement"],
                "automation": item["automation"],
                "impact": item["impact"],
                "complexite": item["complexite"],
                "priorite": priorite,
                "statut": p["statut"],
                "pourquoi": item["pourquoi"],
                "piege": item["piege"],
            }
        )

    plan_rows.sort(key=lambda r: PRIORITY_ORDER[r["priorite"]])

    for row in plan_rows:
        with st.container(border=True):
            st.markdown(f"{PRIORITY_BADGE[row['priorite']]} **Priorité {row['priorite']}** — {row['automation']}")
            st.caption(f"Problème d'origine : {row['problem']} ({row['statut']})")
            st.write(f"Impact : {row['impact']} · Complexité : {row['complexite']}")
            st.write(f"**Pourquoi ça compte** — {row['pourquoi']}")
            st.write(f"**Comment faire** — {comment_faire}")
            st.write(f"**Piège classique à éviter** — {row['piege']}")


def fetch_suivi(token, base_id, table_id, agency_id):
    """Récupère tous les relevés Suivi Avant/Après pour une agence donnée.
    Pas de cache (table faite pour être écrite souvent, on veut la donnée
    fraîche juste après un enregistrement).
    """
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"pageSize": 100}

    records = []
    offset = None
    while True:
        if offset:
            params["offset"] = offset
        else:
            params.pop("offset", None)

        response = requests.get(url, headers=headers, params=params, timeout=15)
        if not response.ok:
            raise RuntimeError(f"Airtable a répondu {response.status_code} — {response.text}")

        data = response.json()
        for record in data.get("records", []):
            fields = record.get("fields", {})
            linked = fields.get(SUIVI_FIELD_AGENCE, [])
            if agency_id not in linked:
                continue
            indicateurs = [
                (fields.get(f"Indicateur {i} - nom"), fields.get(f"Indicateur {i} - valeur"))
                for i in (1, 2, 3)
                if fields.get(f"Indicateur {i} - nom")
            ]
            records.append(
                {
                    "id": record["id"],
                    "date": fields.get(SUIVI_FIELD_DATE, ""),
                    "moment": fields.get(SUIVI_FIELD_MOMENT, ""),
                    "indicateurs": indicateurs,
                    "notes": fields.get(SUIVI_FIELD_NOTES, ""),
                }
            )

        offset = data.get("offset")
        if not offset:
            break

    records.sort(key=lambda r: r["date"])
    return records


def save_suivi_snapshot(token, base_id, table_id, agency, moment, indicators, notes):
    """Écrit un nouveau relevé dans Suivi Avant/Après. Lève une RuntimeError
    avec un message clair (jamais un crash silencieux) sur toute erreur :
    token sans droit d'écriture, Airtable indisponible, etc.
    """
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    date_str = date.today().isoformat()

    fields = {
        SUIVI_FIELD_TITRE: f"{agency['name']} — {moment} — {date_str}",
        SUIVI_FIELD_AGENCE: [agency["id"]],
        SUIVI_FIELD_DATE: date_str,
        SUIVI_FIELD_MOMENT: moment,
    }
    for i, (nom, valeur) in enumerate(indicators, start=1):
        if not nom:
            continue
        fields[f"Indicateur {i} - nom"] = nom
        fields[f"Indicateur {i} - valeur"] = valeur or ""
    if notes:
        fields[SUIVI_FIELD_NOTES] = notes

    try:
        response = requests.post(url, headers=headers, json={"records": [{"fields": fields}]}, timeout=15)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Impossible de contacter Airtable (réseau/service indisponible) : {exc}") from exc

    if not response.ok:
        if response.status_code in (401, 403):
            raise RuntimeError(
                "Airtable a refusé l'écriture (token sans le scope 'data.records:write' ?). "
                "Ajoutez ce scope à votre token existant sur https://airtable.com/create/tokens, "
                "puis réessayez — pas besoin de créer un nouveau token."
            )
        raise RuntimeError(f"Airtable a répondu {response.status_code} — {response.text}")


def render_releve_card(releve):
    st.write(f"📅 {releve['date'] or '(date inconnue)'}")
    for nom, valeur in releve["indicateurs"]:
        st.write(f"- **{nom}** : {valeur or '—'}")
    if releve["notes"]:
        st.caption(releve["notes"])


def render_suivi(agency, token, base_id, suivi_table_id):
    """Étape 5 : suivi avant/après. Affiche les relevés existants pour
    l'agence (côte à côte, sans aucun calcul de delta/ROI) et permet d'en
    ajouter un nouveau. Première écriture Airtable de l'app — toute erreur
    (token sans droit d'écriture, Airtable indisponible) affiche un
    message clair, jamais un crash.
    """
    st.divider()
    st.header("Suivi avant/après")

    try:
        releves = fetch_suivi(token, base_id, suivi_table_id, agency["id"])
    except Exception as exc:
        st.error(f"Impossible de récupérer le suivi depuis Airtable : {exc}")
        releves = None

    if releves is not None:
        avant = [r for r in releves if r["moment"] == "Avant"]
        apres = [r for r in releves if r["moment"] == "Après"]

        if not avant and not apres:
            st.caption("Aucun relevé pour cette agence pour le moment.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Avant")
                if avant:
                    for r in avant:
                        render_releve_card(r)
                else:
                    st.caption("Aucun relevé « avant » pour le moment.")
            with col2:
                st.subheader("Après")
                if apres:
                    for r in apres:
                        render_releve_card(r)
                else:
                    st.caption("Aucun relevé « après » pour le moment.")

    with st.form(key=f"suivi_form_{agency['id']}"):
        st.markdown("**Ajouter un relevé**")
        moment = st.radio("Moment", options=SUIVI_MOMENTS, horizontal=True, key=f"{agency['id']}_suivi_moment")
        ind1_nom = st.text_input("Indicateur 1 — nom", key=f"{agency['id']}_suivi_ind1_nom")
        ind1_val = st.text_input("Indicateur 1 — valeur", key=f"{agency['id']}_suivi_ind1_val")
        ind2_nom = st.text_input("Indicateur 2 — nom (optionnel)", key=f"{agency['id']}_suivi_ind2_nom")
        ind2_val = st.text_input("Indicateur 2 — valeur", key=f"{agency['id']}_suivi_ind2_val")
        ind3_nom = st.text_input("Indicateur 3 — nom (optionnel)", key=f"{agency['id']}_suivi_ind3_nom")
        ind3_val = st.text_input("Indicateur 3 — valeur", key=f"{agency['id']}_suivi_ind3_val")
        notes = st.text_area("Notes", key=f"{agency['id']}_suivi_notes")
        submitted = st.form_submit_button("Enregistrer le relevé")

    if submitted:
        if not ind1_nom.strip():
            st.warning("Renseignez au moins l'indicateur 1 (nom) avant d'enregistrer.")
        else:
            indicators = [(ind1_nom, ind1_val), (ind2_nom, ind2_val), (ind3_nom, ind3_val)]
            try:
                save_suivi_snapshot(token, base_id, suivi_table_id, agency, moment, indicators, notes)
            except Exception as exc:
                st.error(f"Impossible d'enregistrer le relevé dans Airtable : {exc}")
            else:
                st.success(f"Relevé « {moment} » enregistré ✅")
                st.rerun()


def main():
    st.set_page_config(page_title="RAMO — Audit guidé", page_icon="🏠")
    st.title("RAMO")
    st.caption(
        "Étape 1 : Airtable · Étape 2 : audit · Étape 3 : diagnostic · "
        "Étape 4 : plan de solution · Étape 5 : suivi avant/après"
    )

    token = get_config("AIRTABLE_TOKEN")
    base_id = get_config("AIRTABLE_BASE_ID", DEFAULT_BASE_ID)
    table_id = get_config("AIRTABLE_TABLE_ID", DEFAULT_TABLE_ID)
    suivi_table_id = get_config("AIRTABLE_SUIVI_TABLE_ID", DEFAULT_SUIVI_TABLE_ID)

    if not token:
        st.error(
            "AIRTABLE_TOKEN manquant. Copiez `.streamlit/secrets.toml.example` en "
            "`.streamlit/secrets.toml` et renseignez votre Personal Access Token Airtable."
        )
        st.stop()

    try:
        with st.spinner("Chargement des agences…"):
            agencies = fetch_agencies(token, base_id, table_id)
    except Exception as exc:
        st.error(f"Impossible de récupérer les données depuis Airtable : {exc}")
        st.stop()

    agency = render_agency_picker(agencies)
    if agency:
        render_agency_card(agency)
        render_audit_form(agency)
        render_diagnostic(agency)
        render_plan(agency)
        render_suivi(agency, token, base_id, suivi_table_id)


if __name__ == "__main__":
    main()
