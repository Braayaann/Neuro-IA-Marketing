import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleHelp,
  Eye,
  ImagePlus,
  LayoutDashboard,
  LogOut,
  Monitor,
  Plus,
  ShieldCheck,
  Users,
} from "lucide-react";
import { api, post } from "./api";
import { Brand, Button, ErrorBox, Stat, Modal } from "./components/ui";
import { Login } from "./pages/Login";
import { Ads, AdModal } from "./pages/Ads";
import { SessionTable, StudyModal } from "./pages/Sessions";
import { Results } from "./pages/Results";
import { Exhibition } from "./pages/Exhibition";
import { UserModal } from "./pages/Users";

function App() {
  const [user, setUser] = useState(undefined),
    [route, setRoute] = useState(location.hash.slice(1) || "overview"),
    [error, setError] = useState(""),
    [ads, setAds] = useState([]),
    [studies, setStudies] = useState([]),
    [users, setUsers] = useState([]),
    [modal, setModal] = useState(null),
    [toast, setToast] = useState(""),
    [loading, setLoading] = useState(false);
  const go = (r) => {
    location.hash = r;
    setRoute(r);
    setError("");
  };
  const notify = (m) => {
    setToast(m);
    setTimeout(() => setToast(""), 4500);
  };
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [a, s] = await Promise.all([api("/ads"), api("/studies")]);
      setAds(a);
      setStudies(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    api("/auth/me")
      .then((r) => setUser(r.user))
      .catch((e) => {
        setError(e.message);
        setUser(null);
      });
    const listener = () => setRoute(location.hash.slice(1) || "overview");
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  useEffect(() => {
    if (user) refresh();
  }, [user, refresh]);
  useEffect(() => {
    if (route === "users" && user?.role === "admin")
      api("/users")
        .then(setUsers)
        .catch((e) => setError(e.message));
  }, [route, user]);
  if (user === undefined)
    return (
      <div className="boot">
        <Brand />
        <p>Preparando tu espacio…</p>
      </div>
    );
  if (!user)
    return (
      <>
        <Login
          onLogin={(u) => {
            setUser(u);
            go("overview");
          }}
        />
        {error && <div className="globalerror">{error}</div>}
      </>
    );
  if (route.startsWith("exhibit/"))
    return (
      <Exhibition
        id={Number(route.split("/")[1])}
        onExit={async (id) => {
          await refresh();
          go("results/" + id);
        }}
        onBack={() => go("sessions")}
      />
    );
  const nav = [
    ["overview", "Vista general", LayoutDashboard],
    ["ads", "Mis anuncios", ImagePlus],
    ["sessions", "Sesiones", Monitor],
    ["results", "Resultados", BarChart3],
    ...(user.role === "admin" ? [["users", "Cuentas", Users]] : []),
  ];
  const selected = route.split("/")[0];
  const finished = studies.filter((s) => s.status === "completed");
  const title = {
    overview: "Una mirada a tu espacio.",
    ads: "Ideas que merecen ser vistas.",
    sessions: "Cada sesión, una nueva perspectiva.",
    results: "De la mirada a los resultados.",
    users: "Las personas detrás de las ideas.",
  };
  const subtitle = {
    overview: "Gestiona tus campañas y descubre cómo conecta tu contenido.",
    ads: "Crea, organiza y prepara el contenido de tu próxima sesión.",
    sessions: "Prepara tus anuncios, calibra la mirada y comienza a observar.",
    results: "Explora las estimaciones registradas en cada sesión.",
    users: "Administra el acceso y los permisos de tu equipo.",
  };
  async function logout() {
    try {
      await post("/auth/logout");
      setUser(null);
      setAds([]);
      setStudies([]);
      await api("/auth/me");
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand />
        <div className="workspacelabel">ESPACIO DE TRABAJO</div>
        <nav>
          {nav.map(([r, label, Icon]) => (
            <button
              key={r}
              onClick={() => go(r)}
              className={selected === r ? "active" : ""}
            >
              <Icon size={19} />
              {label}
              {r === "ads" && (
                <small>{ads.filter((a) => a.active).length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebarbottom">
          <div className="projectnote">
            <span className="online" />
            PRIMERA VERSIÓN
            <p>
              De las ideas a la evidencia.
              <br />
              Un paso a la vez.
            </p>
          </div>
          <button onClick={() => setModal({ type: "help" })}>
            <CircleHelp size={18} />
            Cómo funciona
          </button>
          <button onClick={logout}>
            <LogOut size={18} />
            Cerrar sesión
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Mi espacio <ChevronRight size={14} />
            <strong>
              {nav.find((n) => n[0] === selected)?.[1] || "Resultados"}
            </strong>
          </div>
          <div className="profile">
            <span className="localchip">
              <i />
              Entorno local
            </span>
            <div className="avatar">{user.name.slice(0, 1)}</div>
            <div>
              <strong>{user.name}</strong>
              <small>
                {user.role === "admin" ? "Administrador" : "Dueño del anuncio"}
              </small>
            </div>
          </div>
        </header>
        <main className="content">
          <div className="pageheading">
            <div>
              <div className="eyebrow">
                NEURO IA /{" "}
                {nav.find((n) => n[0] === selected)?.[1]?.toUpperCase()}
              </div>
              <h1>{title[selected] || title.results}</h1>
              <p>{subtitle[selected] || subtitle.results}</p>
            </div>
            {["overview", "ads", "sessions"].includes(selected) && (
              <Button
                icon={Plus}
                onClick={() =>
                  setModal({ type: selected === "ads" ? "ad" : "study" })
                }
              >
                {selected === "ads" ? "Nuevo anuncio" : "Nueva sesión"}
              </Button>
            )}
            {selected === "users" && (
              <Button icon={Plus} onClick={() => setModal({ type: "user" })}>
                Crear cuenta
              </Button>
            )}
          </div>
          <ErrorBox message={error} />
          {selected === "overview" && (
            <>
              <div className="stats">
                <Stat
                  title="ANUNCIOS ACTIVOS"
                  value={ads.filter((a) => a.active).length}
                  icon={ImagePlus}
                  detail="Contenido listo para conectar"
                />
                <Stat
                  title="SESIONES CREADAS"
                  value={studies.length}
                  icon={Monitor}
                  detail="Cada mirada es un comienzo"
                />
                <Stat
                  title="SESIONES FINALIZADAS"
                  value={finished.length}
                  icon={BarChart3}
                  detail="Resultados disponibles para revisar"
                />
              </div>
              <section className="startbanner">
                <div>
                  <span className="eyebrow">TU PRÓXIMO DESCUBRIMIENTO</span>
                  <h2>Tu contenido. Una nueva perspectiva.</h2>
                  <p>
                    Compara hasta cuatro anuncios y explora la mirada
                    <br className="desktop" /> y las expresiones faciales
                    estimadas.
                  </p>
                  <Button
                    className="white"
                    icon={ArrowRight}
                    onClick={() => setModal({ type: "study" })}
                  >
                    Preparar una sesión
                  </Button>
                </div>
                <div className="bannerart">
                  <div className="ring r1" />
                  <div className="ring r2" />
                  <div className="ring r3" />
                  <Eye size={65} />
                  <span className="artdot d1" />
                  <span className="artdot d2" />
                </div>
              </section>
              <div className="sectionheading">
                <div>
                  <h2>Sesiones recientes</h2>
                  <p>
                    Retoma lo que empezaste o revisa tus últimos resultados.
                  </p>
                </div>
                <button className="textbtn" onClick={() => go("sessions")}>
                  Ver todas <ArrowRight size={16} />
                </button>
              </div>
              <SessionTable
                studies={studies.slice(0, 4)}
                go={go}
                emptyAction={() => setModal({ type: "study" })}
              />
              <div className="footnote">
                <ShieldCheck size={16} />
                <p>
                  Las imágenes de cámara se procesan sin guardarse. Los
                  resultados son estimaciones y requieren validación.
                </p>
              </div>
            </>
          )}
          {selected === "ads" && (
            <Ads
              ads={ads}
              edit={(ad) => setModal({ type: "ad", data: ad })}
              create={() => setModal({ type: "ad" })}
            />
          )}
          {selected === "sessions" && (
            <SessionTable
              studies={studies}
              go={go}
              emptyAction={() => setModal({ type: "study" })}
            />
          )}
          {selected === "results" &&
            (route.includes("/") ? (
              <Results id={Number(route.split("/")[1])} go={go} />
            ) : (
              <SessionTable
                studies={studies.filter((s) =>
                  ["completed", "running"].includes(s.status),
                )}
                go={go}
                results
              />
            ))}
          {selected === "users" && user.role === "admin" && (
            <div className="panel tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>Persona</th>
                    <th>Correo electrónico</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>
                      <span className="sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <strong>{u.name}</strong>
                      </td>
                      <td>{u.email}</td>
                      <td>
                        {u.role === "admin"
                          ? "Administrador"
                          : "Dueño del anuncio"}
                      </td>
                      <td>
                        <span
                          className={
                            "badge " + (u.active ? "ready" : "cancelled")
                          }
                        >
                          {u.active ? "Activa" : "Inactiva"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="textbtn"
                          onClick={() => setModal({ type: "user", data: u })}
                        >
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {loading && (
            <p className="loading" role="status">
              Actualizando datos…
            </p>
          )}
          <footer className="pagefooter">
            <span>NEURO IA MARKETING</span>
            <span>Hecho para entender mejor.</span>
          </footer>
        </main>
      </div>
      {modal?.type === "ad" && (
        <AdModal
          ad={modal.data}
          onClose={() => setModal(null)}
          saved={async () => {
            setModal(null);
            await refresh();
            notify("Anuncio guardado");
          }}
        />
      )}
      {modal?.type === "study" && (
        <StudyModal
          ads={ads.filter((a) => a.active)}
          onClose={() => setModal(null)}
          created={async (s) => {
            setModal(null);
            await refresh();
            go("exhibit/" + s.id);
          }}
          createAd={() => setModal({ type: "ad" })}
        />
      )}
      {modal?.type === "user" && (
        <UserModal
          user={modal.data}
          onClose={() => setModal(null)}
          saved={async () => {
            setModal(null);
            setUsers(await api("/users"));
            notify("Cuenta guardada");
          }}
        />
      )}
      {modal?.type === "help" && (
        <Modal title="Una sesión, paso a paso" onClose={() => setModal(null)}>
          <div className="helpsteps">
            {[
              [
                "01",
                "Prepara tu contenido",
                "Crea anuncios con imágenes o texto y elige entre uno y cuatro.",
              ],
              [
                "02",
                "Calibra la mirada",
                "Una sola persona sigue nueve puntos. Mantén su posición y la cámara centrada arriba.",
              ],
              [
                "03",
                "Muestra los anuncios",
                "La cámara estima mirada y expresiones. Detén la sesión cuando termines.",
              ],
              [
                "04",
                "Revisa los resultados",
                "Compara tiempos estimados, muestras y expresiones; también puedes exportar un CSV.",
              ],
            ].map(([n, t, d]) => (
              <div key={n}>
                <span>{n}</span>
                <section>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </section>
              </div>
            ))}
          </div>
          <p className="muted small">
            La estimación no confirma preferencia ni emociones internas.
            Recalibra para cada persona y si cambia de posición.
          </p>
        </Modal>
      )}
      {toast && (
        <div role="status" className="toast">
          <Check size={17} />
          {toast}
        </div>
      )}
    </div>
  );
}

export { App };
