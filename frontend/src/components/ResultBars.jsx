import React from "react";

const number = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });

export function ResultBars({ label, items, unit }) {
  const maximum = Math.max(0, ...items.map((item) => item.value));
  return (
    <figure className="result-bars" aria-label={label}>
      <figcaption>
        Escala desde 0{maximum > 0 ? ` hasta ${number.format(maximum)}` : ""}{" "}
        {unit}
      </figcaption>
      {!maximum && <p className="small muted">Sin datos suficientes</p>}
      <ul>
        {items.map((item) => (
          <li key={item.key}>
            <div className="result-bar-label">
              <span>{item.label}</span>
              <strong>
                {number.format(item.value)} {unit}
              </strong>
            </div>
            <div className="result-bar-track" aria-hidden="true">
              <span
                style={{
                  width: `${maximum ? (item.value / maximum) * 100 : 0}%`,
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function QuadrantSummary({ ad }) {
  const attributed = ad.quadrant_seconds || 0;
  const quadrants = ad.quadrants || [];
  const largest = Math.max(0, ...quadrants.map((zone) => zone.seconds));
  const leaders = quadrants.filter((zone) => zone.seconds === largest);
  return (
    <>
      <p className="small">
        Se atribuyeron a cuadrantes{" "}
        <strong>{number.format(attributed)} s</strong> de los{" "}
        {number.format(ad.seconds)} s de mirada estimada
        {ad.seconds > 0
          ? ` (${number.format((attributed / ad.seconds) * 100)} %)`
          : ""}
        .
      </p>
      {attributed > 0 && largest > 0 && (
        <p className="quadrant-summary">
          {leaders.length === 1
            ? `La zona ${leaders[0].label.toLowerCase().replace(/o$/, "a")} reunió el ${number.format((largest / attributed) * 100)} % del tiempo atribuido a cuadrantes.`
            : `Las zonas ${leaders.map((zone) => zone.label.toLowerCase().replace(/o$/, "a")).join(", ")} compartieron el mayor tiempo, con ${number.format(largest)} s cada una.`}
        </p>
      )}
      <p className="small muted">
        Los intervalos entre zonas distintas quedan sin atribuir a un cuadrante.
      </p>
    </>
  );
}
