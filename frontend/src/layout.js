export function studyColumns(study) {
  return study.layout_columns ?? Math.min(study.slots.length, 2);
}

export function gridStyle(count, columns) {
  return {
    gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${Math.ceil(count / columns)}, minmax(0, 1fr))`,
  };
}
