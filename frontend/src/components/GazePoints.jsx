import React from "react";
import { AdVisual } from "./ui";

export function GazePoints({ ad, study }) {
  const columns = study.slots.length === 1 ? 1 : 2;
  const rows = study.slots.length > 2 ? 2 : 1;
  const points = (ad.points || [])
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
    .map((p) => ({
      x: p.x * columns - (ad.position % columns),
      y: p.y * rows - Math.floor(ad.position / columns),
    }))
    .filter((p) => p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1);
  const aspect = (study.screen_width || 1200) / columns / ((study.screen_height || 800) / rows);
  return (
    <>
      <div className="gaze-points" style={{ aspectRatio: aspect }}>
        <AdVisual ad={ad} />
        <svg width="100%" height="100%" role="img" aria-label="Mapa de puntos de mirada">
          {points.map((p, index) => (
            <circle key={index} cx={`${p.x * 100}%`} cy={`${p.y * 100}%`}
              r="2" fill="#f05223" fillOpacity="0.65" stroke="white" strokeWidth="0.5" />
          ))}
        </svg>
      </div>
      <p className="small muted" role="status">
        {points.length ? `${points.length} muestras válidas de este anuncio. Cada punto representa una muestra de mirada estimada.`
          : "No hay muestras válidas de mirada para este anuncio."}
      </p>
    </>
  );
}
