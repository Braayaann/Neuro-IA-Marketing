import React, { useState, useEffect, useRef } from "react";
import { Camera, Check, Play, ShieldCheck, Square, Target } from "lucide-react";
import { api, post } from "../api";
import { EMO, REASONS, secs } from "../config";
import { Brand, Button, ErrorBox } from "../components/ui";
import { AdGrid } from "../components/AdGrid";

function Exhibition({ id, onExit, onBack }) {
  const [study, setStudy] = useState(null),
    [error, setError] = useState(""),
    [stream, setStream] = useState(null),
    [captureReady, setCaptureReady] = useState(false),
    [devices, setDevices] = useState([]),
    [camera, setCamera] = useState(""),
    [busy, setBusy] = useState(false),
    [phase, setPhase] = useState("setup"),
    [target, setTarget] = useState(0),
    [count, setCount] = useState(0),
    [sample, setSample] = useState(null),
    [elapsed, setElapsed] = useState(0),
    [status, setStatus] = useState(null);
  const video = useRef(),
    preview = useRef(),
    canvas = useRef(),
    alive = useRef(true),
    cancel = useRef(false),
    seq = useRef(0),
    startTime = useRef(0),
    inflight = useRef(null),
    display = useRef(),
    streamRef = useRef(null);
  const targets = [0.12, 0.5, 0.88].flatMap((y) =>
    [0.12, 0.5, 0.88].map((x) => [x, y]),
  );
  useEffect(() => {
    alive.current = true;
    Promise.all([api("/studies/" + id), api("/vision/status")])
      .then(([s, v]) => {
        setStudy(s);
        setStatus(v);
        if (["completed", "cancelled"].includes(s.status)) onExit(id);
        if (s.status === "running")
          setError(
            "Esta sesión quedó abierta. Finalízala y crea una nueva para recalibrar.",
          );
      })
      .catch((e) => setError(e.message));
    return () => {
      alive.current = false;
      cancel.current = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    };
  }, [id]);
  useEffect(() => {
    if (video.current && video.current.srcObject !== stream) {
      video.current.srcObject = stream;
    }
    if (preview.current && preview.current.srcObject !== stream) {
      preview.current.srcObject = stream;
    }
  }, [stream, phase, study]);
  async function connect() {
    setBusy(true);
    setError("");
    setCaptureReady(false);
    setPhase("setup");
    try {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error("La cámara requiere localhost o HTTPS.");
      const s = await navigator.mediaDevices.getUserMedia({
        video: camera
          ? {
              deviceId: { exact: camera },
              width: { ideal: 640 },
              height: { ideal: 480 },
            }
          : { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      if (!alive.current) {
        s.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = s;
      setStream(s);
      s.getVideoTracks()[0].addEventListener("ended", () => {
        setCaptureReady(false);
        setError(
          "La cámara se desconectó. Detén la sesión y vuelve a conectar.",
        );
        cancel.current = true;
      });
      setDevices(
        (await navigator.mediaDevices.enumerateDevices()).filter(
          (d) => d.kind === "videoinput",
        ),
      );
      setCamera(s.getVideoTracks()[0].getSettings().deviceId || "");
    } catch (e) {
      setStream(null);
      setError(
        e.name === "NotAllowedError"
          ? "Permite el acceso a la cámara en tu navegador."
          : e.name === "NotReadableError"
            ? "La cámara está ocupada. Cierra otras aplicaciones de vídeo."
            : e.message,
      );
    } finally {
      setBusy(false);
    }
  }
  async function frame() {
    if (!streamRef.current?.active || !video.current?.videoWidth)
      throw new Error("La cámara no está lista.");
    const c = canvas.current,
      v = video.current;
    c.width = 640;
    c.height = Math.round((v.videoHeight / v.videoWidth) * 640);
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    return new Promise((resolve, reject) =>
      c.toBlob(
        (b) =>
          b
            ? resolve(b)
            : reject(new Error("No se pudo capturar el fotograma.")),
        "image/jpeg",
        0.8,
      ),
    );
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function calibrate() {
    if (!captureReady) return;
    setBusy(true);
    setError("");
    cancel.current = false;
    try {
      if (display.current.requestFullscreen && !document.fullscreenElement)
        await display.current.requestFullscreen();
      await post(`/studies/${id}/calibration/start`, {
        width: window.innerWidth,
        height: window.innerHeight,
        camera_id: camera,
      });
      setPhase("calibrating");
      for (let i = 0; i < 9; i++) {
        if (cancel.current || !alive.current) return;
        setTarget(i);
        setCount(0);
        await sleep(800);
        const t = performance.now();
        let n = 0;
        while (
          (n < 10 || performance.now() - t < 2000) &&
          performance.now() - t < 14000
        ) {
          if (cancel.current || !alive.current) return;
          const form = new FormData();
          form.append("target", String(i));
          form.append("frame", await frame(), "frame.jpg");
          const r = await post(`/studies/${id}/calibration/sample`, form);
          n = r.count;
          setCount(n);
          setSample(r);
          await sleep(80);
        }
        if (n < 10)
          throw new Error(
            "No hay suficientes muestras del iris. Mantén el rostro visible y repite la calibración.",
          );
      }
      const s = await post(`/studies/${id}/calibration/finish`);
      if (alive.current) {
        setStudy(s);
        setPhase("ready");
        setSample(null);
      }
    } catch (e) {
      if (alive.current) {
        setError(e.message);
        setPhase("setup");
      }
      if (document.fullscreenElement)
        await document.exitFullscreen().catch(() => {});
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  async function run() {
    setError("");
    setBusy(true);
    try {
      if (display.current.requestFullscreen && !document.fullscreenElement)
        await display.current.requestFullscreen();
      const s = await post(`/studies/${id}/start`);
      setStudy(s);
      setPhase("running");
      startTime.current = performance.now();
      cancel.current = false;
      seq.current = 0;
      const loop = (async () => {
        try {
          while (!cancel.current && alive.current) {
            const captured = (performance.now() - startTime.current) / 1000;
            const form = new FormData();
            form.append("seq", String(seq.current++));
            form.append("elapsed", String(captured));
            form.append("frame", await frame(), "frame.jpg");
            setSample(await post(`/studies/${id}/observations`, form));
            setElapsed(captured);
            await sleep(180);
          }
        } catch (e) {
          if (alive.current) {
            cancel.current = true;
            setError(e.message);
          }
        }
      })();
      inflight.current = loop;
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function stop() {
    setBusy(true);
    cancel.current = true;
    try {
      await inflight.current;
      await post(`/studies/${id}/stop`);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (document.fullscreenElement) await document.exitFullscreen();
      onExit(id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  useEffect(() => {
    const visibility = () => {
      if (document.hidden && phase === "running") {
        cancel.current = true;
        setError(
          "La pestaña dejó de estar visible. Finaliza la sesión para revisar lo registrado.",
        );
      }
    };
    const resize = () => {
      if (
        ["running", "ready", "calibrating"].includes(phase) &&
        !document.fullscreenElement
      ) {
        cancel.current = true;
        setError(
          "Saliste de pantalla completa. Para conservar la geometría, finaliza esta sesión o repite la calibración.",
        );
        if (phase === "calibrating" || phase === "ready") setPhase("setup");
      }
    };
    document.addEventListener("visibilitychange", visibility);
    document.addEventListener("fullscreenchange", resize);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      document.removeEventListener("fullscreenchange", resize);
    };
  }, [phase]);
  if (!study)
    return (
      <div className="boot">
        <Brand />
        <ErrorBox message={error} />
        <p>Cargando sesión…</p>
        <Button className="secondary" onClick={onBack}>
          Volver
        </Button>
      </div>
    );
  return (
    <div className="exhibition" ref={display}>
      <canvas ref={canvas} hidden />
      <video
        className="capturevideo"
        ref={video}
        autoPlay
        playsInline
        muted
        aria-hidden="true"
        onLoadedData={() => setCaptureReady(true)}
      />
      <header className="exhibitheader">
        <Brand />
        <div>
          <strong>{study.name}</strong>
          <small>
            Una persona · {study.slots.length} anuncio(s) · Mirada calibrada
          </small>
        </div>
        <div className="exhibitactions">
          {phase === "running" && (
            <span className="recording">
              <i />
              {secs(elapsed)}
            </span>
          )}
          <Button
            className="secondary"
            disabled={busy && phase !== "calibrating"}
            icon={Square}
            onClick={stop}
          >
            {phase === "running" ? "Finalizar sesión" : "Cerrar sesión"}
          </Button>
        </div>
      </header>
      <ErrorBox message={error} />
      {phase === "calibrating" ? (
        <div className="calibrationarea">
          <div className="calibrationnote">
            <Target size={20} />
            <h2>Sigue el punto con la mirada</h2>
            <p>
              Sin mover la cabeza. Punto {target + 1} de 9 · {count}/10 muestras
            </p>
            <small>
              {REASONS[sample?.reason] ||
                "Mantén los ojos abiertos y mira al centro del punto."}
            </small>
          </div>
          <div
            className="target"
            style={{
              left: targets[target][0] * 100 + "%",
              top: targets[target][1] * 100 + "%",
            }}
          >
            <span />
          </div>
          <div className="calibrationprogress">
            {targets.map((_, i) => (
              <i
                key={i}
                className={i < target ? "done" : i === target ? "current" : ""}
              />
            ))}
          </div>
        </div>
      ) : phase === "running" ? (
        <div className="exhibitstage">
          <AdGrid slots={study.slots} />
          <div className="livepill">
            <span className={"online " + (!sample?.valid ? "warning" : "")} />
            {sample?.valid
              ? "Mirada registrada"
              : REASONS[sample?.reason] || "Analizando…"}
            {sample?.emotion && (
              <>
                <span className="pilldivider" />
                {EMO[sample.emotion] || sample.emotion} ·{" "}
                {Math.round(sample.confidence * 100)}%
              </>
            )}
          </div>
        </div>
      ) : (
        <main className="setup">
          <div className="setupheading">
            <span className="eyebrow">ANTES DE EMPEZAR</span>
            <h1>
              {phase === "ready"
                ? "Todo listo para observar."
                : "Preparemos una buena sesión."}
            </h1>
            <p>
              {phase === "ready"
                ? "Mantén la misma posición. Los anuncios ocuparán el área calibrada."
                : "Coloca la cámara centrada arriba de la pantalla y verifica que se vea una sola persona."}
            </p>
          </div>
          <div className="setupgrid">
            <section className="panel">
              <div className="panelhead">
                <h2>Vista de cámara</h2>
                <Camera size={20} />
              </div>
              <div className="camerabox">
                {stream ? (
                  <video ref={preview} autoPlay playsInline muted />
                ) : (
                  <div>
                    <Camera size={38} />
                    <p>Tu cámara está desconectada</p>
                    <small>Actívala para preparar la calibración.</small>
                  </div>
                )}
              </div>
              {devices.length > 1 && (
                <label>
                  Cámara
                  <select
                    value={camera}
                    onChange={(e) => {
                      setCamera(e.target.value);
                      streamRef.current?.getTracks().forEach((t) => t.stop());
                      setStream(null);
                      setCaptureReady(false);
                      setPhase("setup");
                    }}
                  >
                    {devices.map((d) => (
                      <option key={d.deviceId} value={d.deviceId}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <Button
                className="secondary full"
                onClick={connect}
                disabled={busy}
                icon={Camera}
              >
                {stream ? "Reconectar cámara" : "Conectar cámara"}
              </Button>
              <div className="checklist">
                <p>
                  <Check size={16} />
                  Una persona frente a la pantalla, aproximadamente a 1 m.
                </p>
                <p>
                  <Check size={16} />
                  Buena iluminación y ojos visibles.
                </p>
                <p>
                  <Check size={16} />
                  Recalibra si cambia la posición o el tamaño de pantalla.
                </p>
              </div>
            </section>
            <section className="panel">
              <div className="panelhead">
                <h2>Contenido de la sesión</h2>
                <span className="tinybadge">
                  {study.slots.length} anuncio(s)
                </span>
              </div>
              <div className="setuppreview">
                <AdGrid slots={study.slots} />
              </div>
              <div className="visionstatus">
                <span
                  className={"online " + (!status?.mediapipe ? "warning" : "")}
                />
                MediaPipe {status?.mediapipe ? "disponible" : "no disponible"}
                {study.with_emotions && (
                  <span>
                    {" "}
                    · RMN{" "}
                    {status?.weights && status?.torch
                      ? "disponible"
                      : "requiere pesos y PyTorch"}
                  </span>
                )}
              </div>
              <div className="infobox">
                <ShieldCheck size={20} />
                <p>
                  La cámara se procesa en este servidor local. Guardamos
                  coordenadas y clasificaciones; las fotos y los vídeos no se
                  almacenan.
                </p>
              </div>
              {study.status === "running" ? (
                <Button className="full" onClick={stop}>
                  Finalizar sesión abierta
                </Button>
              ) : (
                <>
                  <Button
                    className="full"
                    disabled={
                      !captureReady ||
                      busy ||
                      !status?.enabled ||
                      !status?.mediapipe ||
                      (study.with_emotions &&
                        (!status?.weights || !status?.torch))
                    }
                    onClick={phase === "ready" ? run : calibrate}
                    icon={phase === "ready" ? Play : Target}
                  >
                    {busy
                      ? "Preparando…"
                      : phase === "ready"
                        ? "Iniciar exhibición"
                        : "Calibrar mirada · 9 puntos"}
                  </Button>
                  {phase === "ready" && (
                    <button
                      className="textbtn recalin"
                      onClick={calibrate}
                      disabled={busy}
                    >
                      Repetir calibración
                    </button>
                  )}
                </>
              )}
            </section>
          </div>
        </main>
      )}
    </div>
  );
}

export { Exhibition };
