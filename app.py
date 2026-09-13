"""RAMO — Étape 1 : connexion Airtable (sélection d'agence).
Étape 2 : audit guidé (questionnaire structuré, sans logique de diagnostic).

Aucune donnée n'est dupliquée : on lit en direct la base Airtable existante
("Suivi Prospects Agences" -> table "Agences immobilières"). L'audit guidé
ne fait que capturer des réponses pour l'instant — il n'est pas encore
écrit dans Airtable et ne calcule aucun score (ça viendra à l'étape 3).
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


def main():
    st.set_page_config(page_title="RAMO — Audit guidé", page_icon="🏠")
    st.title("RAMO")
    st.caption("Étape 1 : connexion Airtable · Étape 2 : audit guidé")

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


if __name__ == "__main__":
    main()
