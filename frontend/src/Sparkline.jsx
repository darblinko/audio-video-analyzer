import React from 'react';

const WIDTH = 320;
const HEIGHT = 64;

function Sparkline({ label, unit, times, values, digits = 2 }) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const lastTime = times[times.length - 1] || 1;
  const points = values
    .map((value, i) => {
      const x = (times[i] / lastTime) * WIDTH;
      const y = HEIGHT - ((value - min) / span) * (HEIGHT - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <figure className="sparkline">
      <figcaption>
        {label}: {min.toFixed(digits)} to {max.toFixed(digits)} {unit} over {lastTime.toFixed(1)} s
      </figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${label} over time`}>
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </figure>
  );
}

export default Sparkline;
