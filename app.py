"""RAMO — Étape 1 : connexion Airtable (sélection d'agence).

Une seule chose : choisir une agence dans une liste déroulante et afficher
ses infos de base (nom, ville, score prospect). Aucune donnée n'est
dupliquée : on lit en direct la base Airtable existante
("Suivi Prospects Agences" -> table "Agences immobilières").
"""

import os

import requests
import streamlit as st

FIELD_NAME = "nom de l'agence"
FIELD_CITY = "ville"
FIELD_SCORE = "score prospect"

DEFAULT_BASE_ID = "appsCrRJjuTmuw9Y3"
DEFAULT_TABLE_ID = "tblGWjkwRgKkJIps6"


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


def main():
    st.set_page_config(page_title="RAMO — Sélection d'agence", page_icon="🏠")
    st.title("RAMO — Sélection d'agence")
    st.caption("Étape 1 : connexion Airtable · base « Suivi Prospects Agences »")

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

    names = [a["name"] for a in agencies]
    selected_name = st.selectbox(
        f"Agence ({len(agencies)} au total)",
        options=names,
        index=None,
        placeholder="— Choisir une agence —",
    )

    if selected_name:
        agency = next(a for a in agencies if a["name"] == selected_name)
        st.subheader(agency["name"])
        col1, col2 = st.columns(2)
        col1.metric("Ville", agency["city"] or "Non renseignée")
        col2.metric("Score prospect", agency["score"] if agency["score"] is not None else "—")


if __name__ == "__main__":
    main()
