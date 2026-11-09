import React, { useState, useEffect, useRef, useCallback } from "react";
import { AdVisual } from "./ui";

function Heatmap({ points, children }) {
  const ref = useRef();
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const draw = () => {
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, width, height);
      for (const p of points) {
        const x = p.x * width,
          y = p.y * height;
        const gr = ctx.createRadialGradient(
          x,
          y,
          0,
          x,
          y,
          Math.min(width, height) * 0.09,
        );
        gr.addColorStop(0, "rgba(255,94,30,.15)");
        gr.addColorStop(0.45, "rgba(255,199,40,.06)");
        gr.addColorStop(1, "rgba(255,210,40,0)");
        ctx.fillStyle = gr;
        ctx.fillRect(x - 80, y - 80, 160, 160);
      }
    };
    draw();
    const o = new ResizeObserver(draw);
    o.observe(canvas);
    return () => o.disconnect();
  }, [points]);
  return (
    <div className="heatwrap">
      {children}
      <canvas ref={ref} aria-label="Mapa de densidad de muestras válidas" />
    </div>
  );
}

function AdGrid({ slots }) {
  return (
    <div className={"adgrid n" + slots.length}>
      {slots.map((a) => (
        <div key={a.id} className="adcell">
          <AdVisual ad={a} />
          <span className="adposition">ANUNCIO {a.position + 1}</span>
        </div>
      ))}
    </div>
  );
}

export { Heatmap, AdGrid };
