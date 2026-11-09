import React, { useState, useEffect, useRef, useCallback } from "react";
import { Activity, ArrowRight, ImagePlus, X } from "lucide-react";
import { STATUS } from "../config";

function Brand({ light = false }) {
  return (
    <div className={"brand " + (light ? "light" : "")}>
      <span className="brandmark">
        <Activity size={23} />
      </span>
      <span>
        neuro<span className="brandia">ia</span>
        <small>MARKETING</small>
      </span>
    </div>
  );
}

function Badge({ status }) {
  return (
    <span className={"badge " + status}>
      <i />
      {STATUS[status] || status}
    </span>
  );
}

function Empty({ icon: Icon = ImagePlus, title, children, action }) {
  return (
    <div className="empty">
      <span>
        <Icon size={30} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}

function Button({ children, icon: Icon, className = "", ...props }) {
  return (
    <button className={"btn " + className} {...props}>
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}

function Modal({ title, onClose, children }) {
  const ref = useRef();
  useEffect(() => {
    const before = document.activeElement;
    ref.current?.focus();
    const key = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const els = [
          ...ref.current.querySelectorAll(
            'button,input,textarea,select,[tabindex="0"]',
          ),
        ].filter((e) => !e.disabled);
        if (!els.length) return;
        const first = els[0],
          last = els.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      before?.focus();
    };
  }, []);
  return (
    <div
      className="modalback"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={ref}
      >
        <div className="modalhead">
          <h2>{title}</h2>
          <button className="iconbtn" aria-label="Cerrar" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function ErrorBox({ message }) {
  return (
    message && (
      <div className="error" role="alert">
        {message}
      </div>
    )
  );
}

function AdVisual({ ad, mini = false }) {
  return (
    <div
      className={"advisual " + (mini ? "mini" : "")}
      style={{ background: ad.color || "#c7f36b" }}
    >
      {ad.image_url ? (
        <img src={ad.image_url} alt={ad.title} />
      ) : (
        <>
          <span className="adnoise" />
          <div className="adcopy">
            <span className="adkicker">
              TECNÓPOLIS · CONECTA CON LO QUE VIENE
            </span>
            <h3>{ad.title}</h3>
            <p>{ad.description || "Un espacio para nuevas ideas."}</p>
            <span className="adcta">
              Descubre más <ArrowRight size={16} />
            </span>
          </div>
          <span className="adorbit one" />
          <span className="adorbit two" />
        </>
      )}
    </div>
  );
}

function Stat({ title, value, icon: Icon, detail }) {
  return (
    <section className="stat">
      <div>
        <span>{title}</span>
        <span className="staticon">
          <Icon size={20} />
        </span>
      </div>
      <strong>{String(value).padStart(2, "0")}</strong>
      <p>{detail}</p>
    </section>
  );
}

export { Brand, Badge, Empty, Button, Modal, ErrorBox, AdVisual, Stat };
