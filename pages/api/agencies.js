// Étape 1 — proxy serveur vers Airtable.
// On ne fait jamais d'appel Airtable depuis le navigateur : le token reste
// côté serveur (variable d'environnement), le client ne reçoit que du JSON.

const AIRTABLE_BASE_ID = process.env.AIRTABLE_BASE_ID || "appsCrRJjuTmuw9Y3";
const AIRTABLE_TABLE_ID = process.env.AIRTABLE_TABLE_ID || "tblGWjkwRgKkJIps6";

const FIELD_NAME = "nom de l'agence";
const FIELD_CITY = "ville";
const FIELD_SCORE = "score prospect";

export default async function handler(req, res) {
  const token = process.env.AIRTABLE_TOKEN;

  if (!token) {
    res.status(500).json({
      error:
        "AIRTABLE_TOKEN manquant. Copiez .env.local.example en .env.local et renseignez votre Personal Access Token Airtable.",
    });
    return;
  }

  try {
    const agencies = await fetchAllAgencies(token);
    res.status(200).json({ agencies });
  } catch (err) {
    console.error("Erreur Airtable:", err);
    res.status(502).json({
      error: `Impossible de récupérer les données depuis Airtable : ${err.message}`,
    });
  }
}

async function fetchAllAgencies(token) {
  const results = [];
  let offset;

  do {
    const url = new URL(
      `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`
    );
    url.searchParams.append("fields[]", FIELD_NAME);
    url.searchParams.append("fields[]", FIELD_CITY);
    url.searchParams.append("fields[]", FIELD_SCORE);
    url.searchParams.set("pageSize", "100");
    if (offset) url.searchParams.set("offset", offset);

    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Airtable a répondu ${response.status} — ${body}`);
    }

    const data = await response.json();

    for (const record of data.records) {
      const name = record.fields[FIELD_NAME];
      if (!name) continue; // on ignore les lignes sans nom d'agence (données incomplètes)

      results.push({
        id: record.id,
        name,
        city: record.fields[FIELD_CITY] ?? null,
        score: typeof record.fields[FIELD_SCORE] === "number" ? record.fields[FIELD_SCORE] : null,
      });
    }

    offset = data.offset;
  } while (offset);

  results.sort((a, b) => a.name.localeCompare(b.name, "fr"));
  return results;
}
