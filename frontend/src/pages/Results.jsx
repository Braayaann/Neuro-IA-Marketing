import React, { useState, useEffect, useRef, useCallback } from "react";
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

function Results({ id, go }) {
  const [selectedAd, setSelectedAd] = useState("");
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    setSelectedAd("");
    api("/studies/" + id + "/results")
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id]);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <p>Cargando resultados…</p>;
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
            No se registraron fotogramas durante la exhibición. Puedes preparar
            una nueva sesión y verificar la cámara.
          </Empty>
        </div>
      ) : (
        <>
          <div className="resultgrid">
            <section className="panel">
              <div className="panelhead">
                <h2>Mapa de puntos de mirada</h2>
              </div>
              {data.ads.length > 0 && <>
                <label htmlFor="gaze-ad">Anuncio</label>
                <select id="gaze-ad" value={selectedAd || data.ads[0].id}
                  onChange={(event) => setSelectedAd(event.target.value)}>
                  {data.ads.map((ad) => <option key={ad.id} value={ad.id}>{ad.title}</option>)}
                </select>
                <GazePoints study={data.study}
                  ad={data.ads.find((ad) => String(ad.id) === selectedAd) || data.ads[0]} />
              </>}
            </section>
            <section className="panel">
              <h2>Comparación de anuncios</h2>
              <p className="muted small">
                Distribución del tiempo estimado registrado.
              </p>
              <div className="comparison">
                {data.ads.map((a) => (
                  <div key={a.id}>
                    <div>
                      <strong>{a.title}</strong>
                      <span>{a.share}%</span>
                    </div>
                    <div className="bar">
                      <span
                        style={{ width: a.share + "%", background: a.color }}
                      />
                    </div>
                    <small>
                      {secs(a.seconds)} · {a.samples} muestras válidas
                    </small>
                  </div>
                ))}
              </div>
              <div className="divider" />
              <h3>Expresiones clasificadas</h3>
              {Object.keys(data.emotions).length ? (
                <div className="emotionlist">
                  {Object.entries(data.emotions)
                    .sort((a, b) => b[1] - a[1])
                    .map(([k, v]) => (
                      <div key={k}>
                        <span>{EMO[k] || k}</span>
                        <strong>
                          {v} <small>muestras</small>
                        </strong>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="muted small">
                  Sin expresiones clasificadas en esta sesión.
                </p>
              )}
            </section>
          </div>
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
