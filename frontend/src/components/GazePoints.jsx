import React from "react";
import { studyColumns } from "../layout";
import { AdVisual } from "./ui";

export function GazePoints({
  ad,
  study,
  compact = false,
  showQuadrants = false,
}) {
  const columns = studyColumns(study);
  const rows = Math.ceil(study.slots.length / columns);
  const points = (ad.points || [])
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
    .map((p) => ({
      x: p.x * columns - (ad.position % columns),
      y: p.y * rows - Math.floor(ad.position / columns),
    }))
    .filter((p) => p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1);
  const aspect =
    (study.screen_width || 1200) /
    columns /
    ((study.screen_height || 800) / rows);
  return (
    <>
      <div className="gaze-points" style={{ aspectRatio: aspect }}>
        <AdVisual ad={ad} />
        {showQuadrants && (
          <div
            className="quadrant-overlay"
            aria-label="División en cuatro cuadrantes"
          >
            <span>Superior izquierdo</span>
            <span>Superior derecho</span>
            <span>Inferior izquierdo</span>
            <span>Inferior derecho</span>
          </div>
        )}
        <svg
          width="100%"
          height="100%"
          role="img"
          aria-label="Mapa de puntos de mirada"
        >
          {points.map((p, index) => (
            <circle
              key={index}
              cx={`${p.x * 100}%`}
              cy={`${p.y * 100}%`}
              r="1.5"
              fill="#151b18"
              stroke="#fff"
              strokeWidth="1"
            />
          ))}
        </svg>
      </div>
      {!compact && (
        <p className="small muted" role="status">
          {points.length
            ? `${points.length} muestras válidas de este anuncio. Cada punto representa una muestra de mirada estimada.`
            : "No hay muestras válidas de mirada para este anuncio."}
        </p>
      )}
    </>
  );
}
