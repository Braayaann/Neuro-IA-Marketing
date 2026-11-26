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
import { gridStyle, studyColumns } from "../layout";
import { GazePoints } from "../components/GazePoints";
import { OverviewSummary } from "../components/OverviewSummary";
import { ResultBars, QuadrantSummary } from "../components/ResultBars";

function Results({ id, go }) {
  const [selectedAd, setSelectedAd] = useState("");
  const [showQuadrants, setShowQuadrants] = useState(false);
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
  const columns = studyColumns(data.study);
  const selected = data.ads.find((ad) => String(ad.id) === selectedAd);
  const exportBlock = data.study.export_block_reason;
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
        {exportBlock ? (
          <div>
            <button className="btn secondary" disabled aria-describedby="export-reason">
              <ArrowDownToLine size={17} /> Exportar CSV
            </button>
            <p id="export-reason" className="small muted">{exportBlock}</p>
          </div>
        ) : <a
          className="btn secondary"
          href={"/api/studies/" + id + "/export.csv"}
        >
          <ArrowDownToLine size={17} />
          Exportar CSV
        </a>}
      </div>
      <div className="stats">
        <Stat
          title="TIEMPO ESTIMADO VÁLIDO"
          value={data.valid_samples ? secs(data.estimated_seconds) : "Sin muestras válidas"}
          icon={Eye}
          detail="Intervalos consecutivos por anuncio"
        />
        <Stat
          title="MUESTRAS REGISTRADAS"
          value={data.total_samples}
          icon={Target}
          detail="Fotogramas analizados durante la exhibición"
        />
        <Stat
          title="COBERTURA DE MUESTRAS"
          value={data.valid_ratio + "%"}
          icon={ScanFace}
          detail={`${data.valid_samples} de ${data.total_samples} muestras válidas`}
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
                value: ad.samples ? ad.seconds : null,
              }))}
            />
          </section>
          {!selected && <OverviewSummary ads={data.ads} />}
          <section className="panel">
            <div className="panelhead">
              <h2>Mapa de puntos de mirada</h2>
              <button
                className="btn secondary"
                aria-pressed={showQuadrants}
                onClick={() => setShowQuadrants((shown) => !shown)}
              >
                {showQuadrants ? "Ocultar cuadrantes" : "Mostrar cuadrantes"}
              </button>
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
              <GazePoints
                study={data.study}
                ad={selected}
                showQuadrants={showQuadrants}
              />
            ) : (
              <>
                <div className="gaze-overview" style={gridStyle(data.study.slots.length, columns)}>
                  {data.ads.map((ad) => (
                    <div
                      key={ad.id}
                      className="gaze-overview-cell"
                      style={{
                        gridColumn: ad.position % columns + 1,
                        gridRow: Math.floor(ad.position / columns) + 1,
                      }}
                    >
                      <GazePoints
                        ad={ad}
                        study={data.study}
                        compact
                        showQuadrants={showQuadrants}
                      />
                      <span className="gaze-overview-title">{ad.title}</span>
                    </div>
                  ))}
                  {data.study.slots.length === 3 && columns === 2 && (
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
                    value: selected.samples ? zone.seconds : null,
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
