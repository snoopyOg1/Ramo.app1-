import { useEffect, useMemo, useState } from "react";

export default function Home() {
  const [agencies, setAgencies] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    fetch("/api/agencies")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Erreur inconnue");
        return data.agencies;
      })
      .then((list) => {
        if (cancelled) return;
        setAgencies(list);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setErrorMessage(err.message);
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedAgency = useMemo(
    () => agencies.find((a) => a.id === selectedId) || null,
    [agencies, selectedId]
  );

  return (
    <main>
      <h1>RAMO — Sélection d&apos;agence</h1>
      <p className="subtitle">
        Étape 1 : connexion Airtable · base &laquo; Suivi Prospects Agences &raquo;
      </p>

      {status === "loading" && <p className="status">Chargement des agences…</p>}

      {status === "error" && (
        <p className="status error">
          {errorMessage}
        </p>
      )}

      {status === "ready" && (
        <>
          <label htmlFor="agency-select">
            Agence ({agencies.length} au total)
          </label>
          <select
            id="agency-select"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            <option value="">— Choisir une agence —</option>
            {agencies.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>

          {selectedAgency && (
            <div className="card">
              <h2>{selectedAgency.name}</h2>
              <div className="field-row">
                <span className="field-label">Ville</span>
                <span className="field-value">
                  {selectedAgency.city || <span className="muted">Non renseignée</span>}
                </span>
              </div>
              <div className="field-row">
                <span className="field-label">Score prospect</span>
                <span className="field-value">
                  {selectedAgency.score !== null ? (
                    <span className="score-badge">{selectedAgency.score}</span>
                  ) : (
                    <span className="muted">Non renseigné</span>
                  )}
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </main>
  );
}
