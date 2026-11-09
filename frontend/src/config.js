export const STATUS = {
  draft: "Preparada",
  calibrating: "Calibrando",
  ready: "Calibrada",
  running: "En curso",
  completed: "Finalizada",
  cancelled: "Cancelada",
};
export const EMO = {
  Alegria: "Alegría",
  Enojo: "Enojo",
  Tristeza: "Tristeza",
  Disgusto: "Disgusto",
  Sorpresa: "Sorpresa",
  Miedo: "Miedo",
  Neutral: "Neutral",
};
export const REASONS = {
  sin_rostro: "No se detecta un rostro",
  varios_rostros: "Debe haber una sola persona",
  ojo_cerrado: "Ojo cerrado",
  iris_invalido: "Iris no disponible",
  fuera_de_pantalla: "Mirada fuera del área",
  sin_anuncio: "Área sin anuncio",
};
export const fmtDate = (s) =>
  new Date(s).toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
export const secs = (n) => `${Number(n || 0).toFixed(1)} s`;
