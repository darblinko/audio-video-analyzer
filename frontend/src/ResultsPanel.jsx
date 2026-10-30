import React, { useState } from 'react';
import Sparkline from './Sparkline';

const fixed = (value, digits) => (typeof value === 'number' ? value.toFixed(digits) : 'n/a');
const percent = (value) => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : 'n/a');

function FeatureGroup({ title, rows }) {
  return (
    <div className="feature-section">
      <h4>{title}</h4>
      <ul>
        {rows.map(([name, value]) => (
          <li key={name}>
            {name}: {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AudioFeatures({ features }) {
  const basic = features.basic_info || {};
  const tags = features.classification || {};
  const spectral = features.spectral_features || {};
  const energy = features.energy_features || {};
  const temporal = features.temporal_features || {};
  const hp = features.harmonic_percussive || {};
  const series = features.series;
  return (
    <>
      {series && (
        <div className="series-grid">
          <Sparkline label="RMS energy" unit="" times={series.time_s} values={series.rms} digits={3} />
          <Sparkline label="Spectral centroid" unit="Hz" times={series.time_s} values={series.centroid_hz} digits={0} />
        </div>
      )}
      <div className="features-grid">
        <FeatureGroup title="Clip" rows={[
          ['Duration', `${fixed(basic.duration_seconds, 2)} s`],
          ['Sample rate', `${basic.sample_rate} Hz`],
        ]} />
        <FeatureGroup title="Heuristic tags" rows={[
          ['Type', tags.type], ['Energy', tags.energy_level], ['Tempo', tags.tempo_category],
        ]} />
        <FeatureGroup title="Spectral" rows={[
          ['Centroid mean', `${fixed(spectral.centroid_mean, 1)} Hz`],
          ['Bandwidth mean', `${fixed(spectral.bandwidth_mean, 1)} Hz`],
          ['Rolloff mean', `${fixed(spectral.rolloff_mean, 1)} Hz`],
        ]} />
        <FeatureGroup title="Energy" rows={[
          ['RMS mean', fixed(energy.rms_mean, 4)],
          ['RMS max', fixed(energy.rms_max, 4)],
          ['Max over mean', `${fixed(energy.dynamic_range_db, 2)} dB`],
        ]} />
        <FeatureGroup title="Temporal" rows={[
          ['Zero-crossing rate', fixed(temporal.zero_crossing_rate_mean, 4)],
          ['Tempo', `${fixed(temporal.tempo_bpm, 1)} BPM`],
          ['Beats', temporal.beat_count],
        ]} />
        <FeatureGroup title="Harmonic and percussive" rows={[
          ['Harmonic share', percent(hp.harmonic_ratio)],
          ['Percussive share', percent(hp.percussive_ratio)],
        ]} />
      </div>
    </>
  );
}

function GeminiSection({ analysis }) {
  if (!analysis) return null;
  if (analysis.status !== 'completed') {
    return (
      <div className={`gemini-notice ${analysis.status}`}>
        <h4>Gemini step: {analysis.status.replace('_', ' ')}</h4>
        <p>{analysis.detail}</p>
      </div>
    );
  }
  return (
    <div className="video-analysis">
      <h4>Gemini description ({analysis.model})</h4>
      <p className="analysis-text">{analysis.analysis}</p>
      {analysis.video_info && <p className="result-type">Video: {analysis.video_info.file_size_mb} MB</p>}
    </div>
  );
}

function ResultDetails({ result, onClose }) {
  return (
    <div className="result-details">
      <div className="details-header">
        <h3>{result.filename}</h3>
        <button className="btn-close" onClick={onClose} aria-label="Close details">Close</button>
      </div>
      {result.status === 'failed' && <div className="error-message"><p>{result.error_message}</p></div>}
      {result.status === 'processing' && (
        <div className="processing-message"><div className="spinner"></div><p>Processing</p></div>
      )}
      {result.status === 'completed' && (
        <div className="details-content">
          <GeminiSection analysis={result.video_analysis} />
          {result.audio_features && <AudioFeatures features={result.audio_features} />}
        </div>
      )}
    </div>
  );
}

function ResultsPanel({ results, selectedId, onSelect, onRefresh }) {
  const [closedId, setClosedId] = useState(null);
  const selected = results.find((result) => result.id === selectedId && result.id !== closedId);

  return (
    <div className="results-panel">
      <div className="results-header">
        <h2>Results</h2>
        <button className="btn btn-secondary btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {results.length === 0 ? (
        <div className="empty-state"><p>No results yet. Analyze a sample clip or a recording.</p></div>
      ) : (
        <div className="results-list">
          {results.map((result) => (
            <div
              key={result.id}
              className={`result-item ${selected?.id === result.id ? 'selected' : ''}`}
              onClick={() => { setClosedId(null); onSelect(result.id); }}
            >
              <div className="result-header">
                <h3>{result.filename}</h3>
                <span className={`status-badge ${result.status}`}>{result.status}</span>
              </div>
              <p className="result-timestamp">{new Date(result.upload_timestamp).toLocaleString()}</p>
              <p className="result-type">Type: {result.media_type}</p>
            </div>
          ))}
        </div>
      )}
      {selected && <ResultDetails result={selected} onClose={() => setClosedId(selected.id)} />}
    </div>
  );
}

export default ResultsPanel;
