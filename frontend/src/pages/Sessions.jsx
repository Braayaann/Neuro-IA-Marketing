import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowRight,
  Camera,
  Check,
  ImagePlus,
  Monitor,
  Plus,
} from "lucide-react";
import { post } from "../api";
import { fmtDate } from "../config";
import { Badge, Button, Modal, Empty, ErrorBox } from "../components/ui";

function SessionTable({ studies, go, emptyAction, results = false }) {
  if (!studies.length)
    return (
      <div className="panel">
        <Empty
          icon={Monitor}
          title={
            results ? "Aún no hay resultados" : "Tu primera sesión empieza aquí"
          }
          action={
            emptyAction && (
              <Button icon={Plus} onClick={emptyAction}>
                Preparar sesión
              </Button>
            )
          }
        >
          {results
            ? "Los resultados aparecerán al registrar una sesión."
            : "Prepara tus anuncios y descubre una nueva forma de observar."}
        </Empty>
      </div>
    );
  return (
    <div className="panel tablewrap">
      <table>
        <thead>
          <tr>
            <th>Sesión</th>
            <th>Fecha</th>
            <th>Anuncios</th>
            <th>Estado</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {studies.map((s) => (
            <tr key={s.id}>
              <td>
                <div className="sessionname">
                  <span className="sessionicon">
                    <Monitor size={18} />
                  </span>
                  <div>
                    <strong>{s.name}</strong>
                    <small>SESIÓN #{String(s.id).padStart(3, "0")}</small>
                  </div>
                </div>
              </td>
              <td>{fmtDate(s.created_at)}</td>
              <td>
                <div className="adstack">
                  {s.slots.map((a) => (
                    <span style={{ background: a.color }} key={a.id} />
                  ))}
                  <small>
                    {s.slots.length} anuncio{s.slots.length !== 1 ? "s" : ""}
                  </small>
                </div>
              </td>
              <td>
                <Badge status={s.status} />
              </td>
              <td>
                <button
                  className="textbtn"
                  onClick={() =>
                    go(
                      (results || ["completed", "cancelled"].includes(s.status)
                        ? "results/"
                        : "exhibit/") + s.id,
                    )
                  }
                >
                  {results || ["completed", "cancelled"].includes(s.status)
                    ? "Ver resultados"
                    : "Abrir sesión"}
                  <ArrowRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StudyModal({ ads, onClose, created, createAd }) {
  const [selected, setSelected] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      await created(
        await post("/studies", {
          name: f.get("name"),
          ad_ids: selected,
          with_emotions: f.get("emotions") === "on",
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Prepara una nueva sesión" onClose={onClose}>
      {!ads.length ? (
        <Empty
          title="Primero, tu contenido"
          action={<Button onClick={createAd}>Crear un anuncio</Button>}
        >
          Necesitas al menos un anuncio activo para comenzar.
        </Empty>
      ) : (
        <form onSubmit={submit}>
          <label>
            Nombre de la sesión
            <input
              name="name"
              required
              maxLength={140}
              placeholder="Ej. Comparación de anuncios · noviembre"
            />
          </label>
          <div className="labelrow">
            <strong>Elige los anuncios</strong>
            <small>{selected.length}/4 seleccionados</small>
          </div>
          <div className="adselect">
            {ads.map((a) => (
              <button
                type="button"
                key={a.id}
                className={selected.includes(a.id) ? "selected" : ""}
                disabled={selected.length === 4 && !selected.includes(a.id)}
                onClick={() =>
                  setSelected((v) =>
                    v.includes(a.id)
                      ? v.filter((i) => i !== a.id)
                      : [...v, a.id],
                  )
                }
              >
                <span style={{ background: a.color }}>
                  {selected.includes(a.id) ? (
                    <Check size={17} />
                  ) : (
                    <ImagePlus size={17} />
                  )}
                </span>
                <strong>{a.title}</strong>
                <small>
                  {selected.includes(a.id)
                    ? "0" + (selected.indexOf(a.id) + 1)
                    : ""}
                </small>
              </button>
            ))}
          </div>
          <p className="small muted">
            El orden de selección define las posiciones: de izquierda a derecha
            y de arriba abajo. Con tres anuncios queda un espacio vacío.
          </p>
          <label className="checkbox">
            <input type="checkbox" name="emotions" defaultChecked />
            Analizar también expresiones faciales con RMN
          </label>
          <div className="infobox">
            <Camera size={19} />
            <p>
              Una persona y una cámara. Antes de exhibir, realizaremos la
              calibración de nueve puntos.
            </p>
          </div>
          <ErrorBox message={error} />
          <div className="modalactions">
            <Button type="button" className="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button disabled={busy || !selected.length} icon={ArrowRight}>
              {busy ? "Preparando…" : "Continuar"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

export { SessionTable, StudyModal };
