import React from "react";
import { EMO, secs } from "../config";

function mostFrequent(entries) {
  const maximum = Math.max(0, ...entries.map((entry) => entry.value));
  if (!maximum) return "Sin datos suficientes";
  return entries
    .filter((entry) => entry.value === maximum)
    .map((entry) => entry.label)
    .join(", ");
}

export function OverviewSummary({ ads }) {
  const sorted = [...ads].sort((a, b) => b.seconds - a.seconds);
  const maximum = sorted[0]?.seconds || 0;
  const measured = sorted.filter((ad) => ad.samples > 0);
  const leaders = measured.filter((ad) => ad.seconds === maximum);
  const total = ads.reduce((sum, ad) => sum + ad.seconds, 0);
  return (
    <section className="panel" aria-label="Resumen de todos los anuncios">
      <h2>Resumen de todos los anuncios</h2>
      <p className="quadrant-summary">
        {maximum > 0 && measured.length > 1
          ? leaders.length === 1
            ? `${leaders[0].title} acumuló el mayor tiempo estimado de mirada: ${secs(maximum)} (${((maximum / total) * 100).toFixed(1)} % del tiempo registrado en anuncios).`
            : `${leaders.map((ad) => ad.title).join(", ")} compartieron el mayor tiempo estimado de mirada, con ${secs(maximum)} cada uno.`
          : "Sin datos suficientes para identificar el anuncio con mayor tiempo de mirada."}
      </p>
      <div className="overview-table-scroll">
        <table className="overview-table">
          <thead>
            <tr>
              <th>Anuncio</th>
              <th>Tiempo de mirada</th>
              <th>Zona con más tiempo</th>
              <th>Expresión más frecuente</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((ad) => (
              <tr key={ad.id}>
                <th scope="row">{ad.title}</th>
                <td>{ad.samples ? secs(ad.seconds) : "Sin muestras válidas"}</td>
                <td>
                  {mostFrequent(
                    (ad.quadrants || []).map((zone) => ({
                      label: zone.label,
                      value: zone.seconds,
                    })),
                  )}
                </td>
                <td>
                  {mostFrequent(
                    Object.entries(ad.emotions || {}).map(([key, value]) => ({
                      label: EMO[key] || key,
                      value,
                    })),
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
