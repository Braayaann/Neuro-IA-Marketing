import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowRight,
  ImagePlus,
  MoreHorizontal,
  Plus,
  Search,
} from "lucide-react";
import { api, post } from "../api";
import { AdVisual, Button, Modal, Empty, ErrorBox } from "../components/ui";

function Ads({ ads, edit, create }) {
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
                    aria-label={"Editar " + a.title}
                    onClick={() => edit(a)}
                  >
                    <MoreHorizontal size={21} />
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
    </>
  );
}

function AdModal({ ad, onClose, saved }) {
  const savedId = useRef(ad?.id);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [color, setColor] = useState(ad?.color || "#c7f36b");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const a = await api("/ads" + (savedId.current ? "/" + savedId.current : ""), {
        method: savedId.current ? "PATCH" : "POST",
        body: {
          title: f.get("title"),
          description: f.get("description"),
          color,
          active: f.get("active") === "on",
        },
      });
      savedId.current = a.id;
      const image = f.get("image");
      if (image?.size) {
        const upload = new FormData();
        upload.append("image", image);
        await post("/ads/" + a.id + "/image", upload);
      }
      await saved();
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
          <span>JPG, PNG o WEBP · Hasta 6 MB</span>
          <input
            name="image"
            type="file"
            accept="image/jpeg,image/png,image/webp"
          />
        </label>
        <p className="small muted">
          Si no añades imagen, se mostrará una composición con tu texto y color.
        </p>
        <ErrorBox message={error} />
        <div className="modalactions">
          <Button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={busy}>
            {busy ? "Guardando…" : "Guardar anuncio"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export { Ads, AdModal };
