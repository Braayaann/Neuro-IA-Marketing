// @vitest-environment jsdom
import React from 'react';
import { expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { GazePoints } from '../components/GazePoints';

it('ubica puntos respecto al anuncio y conserva porcentajes al redimensionar', () => {
  const study = { slots: [1, 2, 3], screen_width: 1200, screen_height: 800 };
  const ad = { position: 1, title: 'Segundo', color: '#fff', points: [{ x: .625, y: .375 }] };
  const { container, rerender, getByRole } = render(<GazePoints study={study} ad={ad} />);
  const circle = container.querySelector('circle');
  expect(circle.getAttribute('cx')).toBe('25%');
  expect(circle.getAttribute('cy')).toBe('75%');
  expect(2 * Number(circle.getAttribute('r')) + Number(circle.getAttribute('stroke-width'))).toBe(4);
  container.style.width = '320px';
  rerender(<GazePoints study={study} ad={ad} />);
  expect(container.querySelector('circle').getAttribute('cx')).toBe('25%');
  expect(parseFloat(container.querySelector('.gaze-points').style.aspectRatio)).toBe(1.5);
  rerender(<GazePoints study={study} ad={{ ...ad, position: 2, points: [] }} />);
  expect(container.querySelectorAll('circle')).toHaveLength(0);
  expect(getByRole('status').textContent).toContain('No hay muestras válidas');
});
