import React, { useState, useEffect, useRef, useCallback } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { post } from "../api";
import { Brand, Button, ErrorBox } from "../components/ui";

function Login({ onLogin }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const data = new FormData(e.currentTarget);
    try {
      const r = await post("/auth/login", Object.fromEntries(data));
      onLogin(r.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <section className="loginart">
        <Brand light />
        <div>
          <span className="eyebrow">OBSERVA. ENTIENDE. CONECTA.</span>
          <h1>
            Cada mirada
            <br />
            cuenta una <em>historia.</em>
          </h1>
          <p>
            Explora cómo las personas interactúan con tus anuncios, desde una
            nueva perspectiva.
          </p>
          <div className="eyeart">
            <div className="eyeouter">
              <div className="eyeiris">
                <span />
              </div>
            </div>
            <div className="cross a" />
            <div className="cross b" />
            <span className="artlabel">UNA NUEVA FORMA DE VER</span>
          </div>
        </div>
        <footer>
          NEURO IA MARKETING <span>Proyecto IV · Universidad de Tarapacá</span>
        </footer>
      </section>
      <section className="loginform">
        <div className="loginbox">
          <span className="eyebrow">TU ESPACIO DE ANÁLISIS</span>
          <h2>Bienvenido de nuevo.</h2>
          <p>Ingresa para gestionar tus anuncios y sesiones.</p>
          <form onSubmit={submit}>
            <label>
              Correo electrónico
              <input
                required
                name="email"
                type="email"
                autoComplete="username"
                placeholder="tu@correo.cl"
              />
            </label>
            <label>
              Contraseña
              <input
                required
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Ingresa tu contraseña"
              />
            </label>
            <ErrorBox message={error} />
            <Button type="submit" disabled={busy}>
              {busy ? "Ingresando…" : "Entrar a mi espacio"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <div className="loginhint">
            <ShieldCheck size={18} />
            <span>Acceso privado. Solicita tu cuenta al administrador.</span>
          </div>
        </div>
        <small className="loginbottom">
          Tecnópolis-Ai · Inteligencia para conectar mejor
        </small>
      </section>
    </main>
  );
}

export { Login };
