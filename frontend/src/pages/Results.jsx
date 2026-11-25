import React, { useState, useEffect } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  BarChart3,
  CircleHelp,
  Eye,
  ScanFace,
  Target,
} from "lucide-react";
import { api } from "../api";
import { EMO, REASONS, secs } from "../config";
import { Badge, Empty, Stat, ErrorBox } from "../components/ui";
import { GazePoints } from "../components/GazePoints";
import { ResultBars, QuadrantSummary } from "../components/ResultBars";

function Results({ id, go }) {
  const [selectedAd, setSelectedAd] = useState("");
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    setError("");
    setSelectedAd("");
    api("/studies/" + id + "/results")
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id]);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <p>Cargando resultados…</p>;
  const selected = data.ads.find((ad) => String(ad.id) === selectedAd);
  return (
    <>
      <div className="resultbar">
        <div>
          <button className="textbtn" onClick={() => go("results")}>
            <ArrowLeft size={16} />
            Todos los resultados
          </button>
          <h2>{data.study.name}</h2>
          <Badge status={data.study.status} />
        </div>
        <a
          className="btn secondary"
          href={"/api/studies/" + id + "/export.csv"}
        >
          <ArrowDownToLine size={17} />
          Exportar CSV
        </a>
      </div>
      <div className="stats">
        <Stat
          title="TIEMPO ESTIMADO VÁLIDO"
          value={secs(data.estimated_seconds)}
          icon={Eye}
          detail="Intervalos consecutivos por anuncio"
        />
        <Stat
          title="MUESTRAS VÁLIDAS"
          value={data.valid_samples}
          icon={Target}
          detail={`De ${data.total_samples} muestras registradas`}
        />
        <Stat
          title="COBERTURA DE MUESTRAS"
          value={data.valid_ratio + "%"}
          icon={ScanFace}
          detail="Muestras asignadas a un anuncio"
        />
      </div>
      {!data.total_samples ? (
        <div className="panel">
          <Empty icon={BarChart3} title="Esta sesión no tiene observaciones">
            Sin datos suficientes. No se registraron fotogramas durante la
            exhibición. Puedes preparar una nueva sesión y verificar la cámara.
          </Empty>
        </div>
      ) : (
        <>
          <section className="panel">
            <h2>Tiempo estimado de mirada por anuncio</h2>
            <ResultBars
              label="Comparación de anuncios en segundos"
              unit="s"
              items={data.ads.map((ad) => ({
                key: ad.id,
                label: ad.title,
                value: ad.seconds,
              }))}
            />
          </section>
          <section className="panel">
            <div className="panelhead">
              <h2>Mapa de puntos de mirada</h2>
            </div>
            <label htmlFor="gaze-ad">Vista del mapa</label>
            <select
              id="gaze-ad"
              value={selectedAd}
              onChange={(event) => setSelectedAd(event.target.value)}
            >
              <option value="">Todos los anuncios</option>
              {data.ads.map((ad) => (
                <option key={ad.id} value={ad.id}>
                  {ad.title}
                </option>
              ))}
            </select>
            {selected ? (
              <GazePoints study={data.study} ad={selected} />
            ) : (
              <>
                <div className={"gaze-overview n" + data.study.slots.length}>
                  {data.ads.map((ad) => (
                    <div
                      key={ad.id}
                      className="gaze-overview-cell"
                      style={{
                        gridColumn:
                          data.study.slots.length === 1
                            ? 1
                            : (ad.position % 2) + 1,
                        gridRow:
                          data.study.slots.length > 2
                            ? Math.floor(ad.position / 2) + 1
                            : 1,
                      }}
                    >
                      <GazePoints ad={ad} study={data.study} compact />
                      <span className="gaze-overview-title">{ad.title}</span>
                    </div>
                  ))}
                  {data.study.slots.length === 3 && (
                    <div className="gaze-unused">Área sin anuncio</div>
                  )}
                </div>
                <p className="small muted">
                  Cada punto representa una muestra válida de mirada estimada.
                  Selecciona un anuncio para revisar sus cuadrantes y
                  expresiones.
                </p>
                {!data.valid_samples && (
                  <p className="small muted" role="status">
                    Sin datos suficientes. No hay muestras válidas de mirada.
                  </p>
                )}
              </>
            )}
          </section>
          {selected && (
            <div className="resultgrid">
              <section className="panel">
                <h2>Tiempo de mirada por cuadrante</h2>
                <ResultBars
                  label="Segundos por cuadrante"
                  unit="s"
                  items={(selected.quadrants || []).map((zone) => ({
                    key: zone.key,
                    label: zone.label,
                    value: zone.seconds,
                  }))}
                />
                <QuadrantSummary ad={selected} />
              </section>
              <section className="panel">
                <h2>Expresiones faciales detectadas</h2>
                <ResultBars
                  label="Frecuencia de expresiones del anuncio"
                  unit="muestras"
                  items={Object.entries(selected.emotions || {})
                    .sort((a, b) => b[1] - a[1])
                    .map(([key, value]) => ({
                      key,
                      label: EMO[key] || key,
                      value,
                    }))}
                />
              </section>
            </div>
          )}
          <section className="panel">
            <h2>Calidad del registro</h2>
            {Object.keys(data.rejected).length ? (
              <div className="qualitylist">
                {Object.entries(data.rejected).map(([k, v]) => (
                  <span key={k}>
                    {REASONS[k] || k}: <strong>{v}</strong>
                  </span>
                ))}
              </div>
            ) : (
              <p className="small muted">No hubo muestras rechazadas.</p>
            )}
            <p className="small muted">
              Se suman intervalos de hasta 1,5 s entre muestras válidas
              consecutivas del mismo anuncio. Los cambios de anuncio y las
              pérdidas de seguimiento interrumpen la suma.
            </p>
          </section>
        </>
      )}
      <div className="infobox">
        <CircleHelp size={20} />
        <p>
          {data.warning} Una calibración completa tampoco demuestra precisión.
        </p>
      </div>
    </>
  );
}

export { Results };
