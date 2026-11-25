// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Results } from "../pages/Results";
import { api } from "../api";

vi.mock("../api", () => ({ api: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function results(valid = true) {
  const labels = [
    "Superior izquierdo",
    "Superior derecho",
    "Inferior izquierdo",
    "Inferior derecho",
  ];
  const ads = [0, 1, 2].map((position) => ({
    id: position + 1,
    position,
    title: `Anuncio ${position + 1}`,
    seconds: valid ? 10 + position : 0,
    quadrant_seconds: valid ? 8 : 0,
    quadrants: labels.map((label, index) => ({
      key: String(index),
      label,
      seconds: valid ? [1, 4, 2, 1][index] : 0,
    })),
    points: valid
      ? [{ x: position === 1 ? 0.75 : 0.25, y: position === 2 ? 0.75 : 0.25 }]
      : [],
    emotions: valid
      ? { [position === 0 ? "Alegria" : "Neutral"]: position + 2 }
      : {},
  }));
  return {
    study: {
      name: "Prueba de tres anuncios",
      status: "completed",
      slots: ads,
      screen_width: 1200,
      screen_height: 800,
    },
    ads,
    valid_samples: valid ? 3 : 0,
    total_samples: 5,
    valid_ratio: valid ? 60 : 0,
    estimated_seconds: valid ? 33 : 0,
    rejected: {},
    warning: "Estimación",
  };
}

it("muestra los tres anuncios y cambia los gráficos y puntos al seleccionar uno", async () => {
  api.mockResolvedValue(results());
  const user = userEvent.setup();
  const { container } = render(<Results id={1} go={vi.fn()} />);
  const selector = await screen.findByLabelText("Vista del mapa");
  expect(container.querySelectorAll(".gaze-points circle")).toHaveLength(3);
  const comparison = screen.getByRole("figure", {
    name: "Comparación de anuncios en segundos",
  });
  expect(within(comparison).getByText("12 s")).toBeTruthy();
  expect(screen.getByText("Área sin anuncio")).toBeTruthy();
  await user.selectOptions(selector, "1");
  expect(container.querySelectorAll(".gaze-points circle")).toHaveLength(1);
  const zones = screen.getByRole("figure", { name: "Segundos por cuadrante" });
  expect(within(zones).getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getByText(/superior derecha reunió el 50 %/)).toBeTruthy();
  const expressions = screen.getByRole("figure", {
    name: "Frecuencia de expresiones del anuncio",
  });
  expect(within(expressions).getByText("Alegría")).toBeTruthy();
  await user.selectOptions(selector, "3");
  expect(within(expressions).queryByText("Alegría")).toBeNull();
  expect(within(expressions).getByText("Neutral")).toBeTruthy();
  await user.selectOptions(selector, "");
  expect(container.querySelectorAll(".gaze-points circle")).toHaveLength(3);
});

it("comunica ausencia de datos en una sesión con todas las muestras inválidas", async () => {
  api.mockResolvedValue(results(false));
  const user = userEvent.setup();
  const { container } = render(<Results id={1} go={vi.fn()} />);
  const selector = await screen.findByLabelText("Vista del mapa");
  expect(screen.getByRole("status").textContent).toContain(
    "Sin datos suficientes",
  );
  expect(container.querySelectorAll(".gaze-points circle")).toHaveLength(0);
  await user.selectOptions(selector, "2");
  expect(screen.getAllByText("Sin datos suficientes")).toHaveLength(3);
  expect(screen.queryByText(/reunió el/)).toBeNull();
  expect(container.textContent).not.toMatch(/NaN|Infinity/);
});
