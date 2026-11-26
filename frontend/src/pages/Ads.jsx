import React, { useState, useEffect, useRef } from "react";
import {
  ArrowRight,
  ImagePlus,
  Trash2,
  Plus,
  Search,
} from "lucide-react";
import { api } from "../api";
import { AdVisual, Button, Modal, Empty, ErrorBox } from "../components/ui";

function Ads({ ads, edit, create, onDeleted }) {
  const [target, setTarget] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const deleting = useRef(false);
  function dismiss() {
    if (!deleting.current) setTarget(null);
  }
  async function remove() {
    if (deleting.current) return;
    deleting.current = true;
    setBusy(true);
    setError("");
    try {
      await api("/ads/" + target.id, { method: "DELETE" });
      onDeleted(target.id);
      setTarget(null);
    } catch (e) {
      setError(e.message);
    } finally {
      deleting.current = false;
      setBusy(false);
    }
  }
  const [search, setSearch] = useState(""),
    [archived, setArchived] = useState(false);
  const filtered = ads.filter(
    (a) =>
      a.active !== archived &&
      a.title.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="toolbar">
        <div className="tabs">
          <button
            className={!archived ? "active" : ""}
            onClick={() => setArchived(false)}
          >
            Activos <span>{ads.filter((a) => a.active).length}</span>
          </button>
          <button
            className={archived ? "active" : ""}
            onClick={() => setArchived(true)}
          >
            Archivados
          </button>
        </div>
        <label className="search">
          <Search size={17} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar anuncio…"
            aria-label="Buscar anuncio"
          />
        </label>
      </div>
      {filtered.length ? (
        <div className="adcards">
          {filtered.map((a) => (
            <article className="adcard" key={a.id}>
              <AdVisual ad={a} mini />
              <div className="adcardbody">
                <div>
                  <h3>{a.title}</h3>
                  <button
                    className="iconbtn"
                    aria-label={"Eliminar " + a.title}
                    title="Eliminar anuncio"
                    onClick={() => { setError(""); setTarget(a); }}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                  </button>
                </div>
                <p>{a.description || "Sin descripción"}</p>
                <footer>
                  <span className="tinybadge">
                    {a.active ? "Disponible para sesión" : "Archivado"}
                  </span>
                  <button className="textbtn" onClick={() => edit(a)}>
                    Editar <ArrowRight size={14} />
                  </button>
                </footer>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="panel">
          <Empty
            title={
              search
                ? "Sin coincidencias"
                : archived
                  ? "No hay anuncios archivados"
                  : "Dale forma a tu primera idea"
            }
            action={
              !archived &&
              !search && (
                <Button icon={Plus} onClick={create}>
                  Crear anuncio
                </Button>
              )
            }
          >
            {search
              ? "Prueba buscando otro título."
              : "Crea un anuncio con una imagen o utiliza una composición de texto."}
          </Empty>
        </div>
      )}
      {target && <Modal title="Eliminar anuncio" onClose={dismiss}>
        <p>¿Seguro que quieres eliminar <strong>«{target.title}»</strong> de Mis anuncios? Las sesiones que ya lo incluyen conservarán su copia.</p>
        <ErrorBox message={error} />
        <div className="modalactions">
          <Button className="secondary" onClick={dismiss} disabled={busy}>Cancelar</Button>
          <Button className="danger" onClick={remove} disabled={busy}>Eliminar anuncio</Button>
        </div>
      </Modal>}
    </>
  );
}

function AdModal({ ad, onClose, saved }) {
  const fileInput = useRef(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [file, setFile] = useState(null),
    [preview, setPreview] = useState(null),
    [color, setColor] = useState(ad?.color || "#c7f36b");
  useEffect(() => {
    if (!file) return;
    let message;
    if (file.size > 6 * 1024 * 1024) message = "La imagen supera el límite de 6 MB.";
    else if (file.type && !["image/jpeg", "image/png", "image/webp"].includes(file.type))
      message = "Formato incompatible. Usa JPG, PNG o WEBP.";
    if (message) {
      setPreview({ file, error: message });
      return;
    }
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      if (image.naturalWidth * image.naturalHeight > 20_000_000)
        setPreview({ file, error: "La imagen supera el límite de 20 megapíxeles." });
      else setPreview({ file, url });
    };
    image.onerror = () => setPreview({ file, error: "Imagen dañada o incompatible. Elige otro archivo." });
    image.src = url;
    return () => {
      image.onload = image.onerror = null;
      URL.revokeObjectURL(url);
    };
  }, [file]);
  const checked = file && preview?.file === file ? preview : null;
  const previewUrl = checked?.url || ad?.image_url;
  async function submit(e) {
    e.preventDefault();
    if (busy || (file && !checked?.url)) return;
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const fields = {
        title: f.get("title"),
        description: f.get("description"),
        color,
        active: f.get("active") === "on",
      };
      let body = fields;
      if (file) {
        body = new FormData();
        for (const [key, value] of Object.entries(fields)) body.append(key, value);
        body.append("image", file);
      }
      const result = await api(ad ? "/ads/" + ad.id : "/ads", {
        method: ad ? "PATCH" : "POST", body,
      });
      await saved(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={ad ? "Editar anuncio" : "Una nueva idea empieza aquí"}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <label>
          Título del anuncio
          <input
            name="title"
            required
            maxLength={140}
            defaultValue={ad?.title}
            placeholder="Ej. Conecta con lo que viene"
          />
        </label>
        <label>
          Descripción
          <textarea
            name="description"
            rows={3}
            maxLength={500}
            defaultValue={ad?.description}
            placeholder="El mensaje que quieres compartir…"
          />
        </label>
        <div className="fieldrow">
          <label>
            Color de fondo
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              name="active"
              defaultChecked={ad?.active ?? true}
            />
            Anuncio activo
          </label>
        </div>
        <label className="uploadlabel">
          <ImagePlus size={24} />
          <strong>
            {ad?.image_url ? "Reemplazar imagen" : "Añadir una imagen"}
          </strong>
          <span>JPG, PNG o WEBP · Hasta 6 MB y 20 megapíxeles</span>
          <input
            name="image"
            type="file"
            ref={fileInput}
            accept="image/jpeg,image/png,image/webp"
            disabled={busy}
            onChange={(e) => {
              setError("");
              setPreview(null);
              setFile(e.target.files[0] || null);
            }}
          />
        </label>
        {file && (
          <div className="file-choice">
            <span aria-live="polite">{file.name}{!checked && " · Comprobando imagen…"}</span>
            <button type="button" className="textbtn" disabled={busy} onClick={() => {
              fileInput.current.value = "";
              setFile(null);
              setPreview(null);
              setError("");
            }}>Descartar archivo</button>
          </div>
        )}
        {previewUrl && <img className="ad-file-preview" src={previewUrl}
          alt={checked?.url ? "Vista previa de la imagen seleccionada" : "Imagen actual del anuncio"} />}
        <ErrorBox message={checked?.error} />
        <p className="small muted">
          Si no añades imagen, se mostrará una composición con tu texto y color.
        </p>
        <ErrorBox message={error} />
        <div className="modalactions">
          <Button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={busy || Boolean(file && !checked?.url)}>
            {busy ? "Guardando…" : "Guardar anuncio"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export { Ads, AdModal };
