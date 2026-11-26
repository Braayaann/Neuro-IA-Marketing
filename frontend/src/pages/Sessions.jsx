import React, { useRef, useState } from "react";
import {
  ArrowRight,
  Trash2,
  Camera,
  ImagePlus,
  Monitor,
  Plus,
} from "lucide-react";
import { AdGrid } from "../components/AdGrid";
import { api, post } from "../api";
import { AdModal } from "./Ads";
import { fmtDate } from "../config";
import { Badge, Button, Modal, Empty, ErrorBox } from "../components/ui";

function SessionTable({ studies, go, emptyAction, results = false, ownerId, onDelete }) {
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
            {onDelete && <th scope="col"><span className="sr-only">Eliminar</span></th>}
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
              {onDelete && <td className="study-delete-cell">
                {s.owner_id === ownerId && s.status !== "running" && (
                  <button className="iconbtn delete-study" aria-label="Eliminar sesión"
                    title={`Eliminar sesión «${s.name}»`} onClick={() => onDelete(s)}>
                    <Trash2 size={13} strokeWidth={1.5} aria-hidden="true" />
                  </button>
                )}
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StudyList({ studies, onDeleted, ...props }) {
  const [filter, setFilter] = useState("all");
  const [target, setTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const deleting = useRef(false);
  const visible = filter === "all" ? studies : studies.filter((s) => s.status === filter);
  function dismiss() {
    if (!deleting.current) setTarget(null);
  }
  async function remove() {
    if (deleting.current) return;
    deleting.current = true;
    setBusy(true);
    setError("");
    try {
      await api("/studies/" + target.id, { method: "DELETE" });
      onDeleted(target.id);
      setTarget(null);
    } catch (e) {
      setError(e.message);
    } finally {
      deleting.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <label className="study-filter">Filtrar por estado
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">Todas</option>
          <option value="completed">Finalizadas</option>
          <option value="cancelled">Canceladas</option>
        </select>
      </label>
      {filter !== "all" && !visible.length ? (
        <p role="status">No hay sesiones con este estado.</p>
      ) : (
        <SessionTable {...props} studies={visible} onDelete={(s) => { setError(""); setTarget(s); }} />
      )}
      {target && (
        <Modal title="Eliminar sesión" onClose={dismiss}>
          <p>¿Quieres eliminar la sesión <strong>«{target.name}»</strong>? También se eliminarán sus resultados. Esta acción es permanente.</p>
          <ErrorBox message={error} />
          <div className="modalactions">
            <Button className="secondary" disabled={busy} onClick={dismiss}>Cancelar</Button>
            <Button className="danger" disabled={busy} onClick={remove}>Eliminar sesión</Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function AdPicker({ ads, selected, setSelected }) {
  const slots = selected.map((id, position) => ({
    ...ads.find((ad) => ad.id === id), position,
  }));
  return (
    <>
      <div className="labelrow">
        <strong>Elige los anuncios</strong>
        <small>{selected.length}/4 seleccionados</small>
      </div>
      <div className="adselect">
        {ads.filter((ad) => ad.active !== false || selected.includes(ad.id)).map((ad) => {
          const index = selected.indexOf(ad.id);
          return (
            <button type="button" key={ad.id} aria-pressed={index >= 0}
              className={index >= 0 ? "selected" : ""}
              disabled={selected.length === 4 && index < 0}
              onClick={() => setSelected(index >= 0 ? selected.filter((id) => id !== ad.id) : [...selected, ad.id])}>
              <span className="ad-thumb">
                {ad.image_url ? <img src={ad.image_url} alt="" /> : <ImagePlus size={18} />}
              </span>
              <strong>{ad.title}{ad.active === false && " (archivado)"}</strong>
              {index >= 0 && <small>{index + 1}</small>}
            </button>
          );
        })}
      </div>
      {slots.length > 0 && (
        <div className="selection-preview" aria-label="Vista previa de la distribución">
          <AdGrid columns={slots.length === 4 ? 2 : slots.length} slots={slots} />
        </div>
      )}
      <p className="small muted">Los anuncios se muestran en el orden de selección, de izquierda a derecha y de arriba abajo.</p>
    </>
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
          <AdPicker ads={ads} selected={selected} setSelected={setSelected} />
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

function StudyAdEditor({ study, ads, onAdSaved, onSave, onClose }) {
  const [selected, setSelected] = useState(() => study.slots.map((slot) => slot.ad_id).filter((id) => id != null));
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setError("");
    try {
      onSave(await api("/studies/" + study.id + "/ads", {
        method: "PATCH", body: { ad_ids: selected },
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (editor) return (
    <AdModal ad={editor.ad} onClose={() => setEditor(null)} saved={(ad) => {
      onAdSaved(ad);
      if (!ad.active) setSelected(selected.filter((id) => id !== ad.id));
      else if (!editor.ad && selected.length < 4) setSelected([...selected, ad.id]);
      setEditor(null);
    }} />
  );
  return (
    <Modal title="Modificar anuncios de la sesión" onClose={onClose}>
      {study.slots.some((slot) => slot.ad_id == null) && (
        <p>Hay anuncios eliminados del catálogo. Al guardar se usarán únicamente los anuncios seleccionados aquí.</p>
      )}
      <AdPicker ads={ads} selected={selected} setSelected={setSelected} />
      <Button className="secondary" icon={Plus} onClick={() => setEditor({})}>Crear anuncio</Button>
      {selected.map((id) => {
        const ad = ads.find((item) => item.id === id);
        return ad && <button key={id} className="textbtn edit-selected-ad"
          onClick={() => setEditor({ ad })}>Editar {ad.title}</button>;
      })}
      <p className="small muted">Al editar un anuncio, se guarda en Mis anuncios. Pulsa Guardar selección para usar los cambios en esta sesión.</p>
      <ErrorBox message={error} />
      <div className="modalactions">
        <Button className="secondary" onClick={onClose}>Cancelar</Button>
        <Button disabled={busy || !selected.length} onClick={save}>
          {busy ? "Guardando…" : "Guardar selección"}
        </Button>
      </div>
    </Modal>
  );
}

export { SessionTable, StudyList, StudyModal, StudyAdEditor };
