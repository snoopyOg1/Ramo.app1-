"""RAMO — Étape 1 : connexion Airtable (sélection d'agence).
Étape 2 : audit guidé (questionnaire structuré).
Étape 3 : diagnostic (reformulation des réponses en problèmes, sans score).

Aucune donnée n'est dupliquée : on lit en direct la base Airtable existante
("Suivi Prospects Agences" -> table "Agences immobilières"). L'audit et le
diagnostic ne font que capturer/reformuler des réponses pour l'instant —
rien n'est encore écrit dans Airtable et aucun score n'est calculé (ça
viendra à l'étape 4, avec le plan de solution).
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
}

# Questions de l'audit dont la réponse est contextuelle (pas un choix fermé
# problème/non-problème) : affichées telles quelles dans le diagnostic,
# sans statut fait/hypothèse ni classement en "problème".
CONTEXT_QUESTION_KEYS = ["outil_suivi_leads", "nombre_agents", "volume_leads_mensuel"]


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

    problems_by_section = {}
    current_section = None
    for q in AUDIT_QUESTIONS:
        if q["section"] != current_section:
            current_section = q["section"]
        options_map = PROBLEM_STATEMENTS.get(q["key"])
        if not options_map:
            continue
        answer = saved["answers"].get(q["key"])
        if not answer:
            continue
        statement = options_map.get(answer["reponse"])
        if not statement:
            continue  # réponse donnée, mais pas une réponse "à problème"
        problems_by_section.setdefault(q["section"], []).append(
            {"statement": statement, "statut": answer["statut"]}
        )

    total_problems = sum(len(v) for v in problems_by_section.values())
    if total_problems == 0:
        st.success("Aucun problème identifié à partir des réponses de l'audit.")
    else:
        st.write(f"**{total_problems} problème(s) identifié(s)**")
        for section, problems in problems_by_section.items():
            st.markdown(f"**{section}**")
            for p in problems:
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


def main():
    st.set_page_config(page_title="RAMO — Audit guidé", page_icon="🏠")
    st.title("RAMO")
    st.caption("Étape 1 : connexion Airtable · Étape 2 : audit guidé · Étape 3 : diagnostic")

    token = get_config("AIRTABLE_TOKEN")
    base_id = get_config("AIRTABLE_BASE_ID", DEFAULT_BASE_ID)
    table_id = get_config("AIRTABLE_TABLE_ID", DEFAULT_TABLE_ID)

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


if __name__ == "__main__":
    main()
