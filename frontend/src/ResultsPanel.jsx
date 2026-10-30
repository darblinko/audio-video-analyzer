import React, { useState } from 'react';

function ResultsPanel({ results, onRefresh }) {
  const [selectedResult, setSelectedResult] = useState(null);
  const [expandedSection, setExpandedSection] = useState('audio');

  const formatTimestamp = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const renderAudioFeatures = (features) => {
    if (!features) return <p>No audio features available</p>;

    return (
      <div className="features-grid">
        <div className="feature-section">
          <h4>📊 Basic Info</h4>
          <ul>
            <li>Duration: {features.basic_info?.duration_seconds?.toFixed(2)}s</li>
            <li>Sample Rate: {features.basic_info?.sample_rate} Hz</li>
            <li>Channels: {features.basic_info?.channels}</li>
          </ul>
        </div>

        <div className="feature-section">
          <h4>🎵 Classification</h4>
          <ul>
            <li>Type: {features.classification?.type}</li>
            <li>Energy: {features.classification?.energy_level}</li>
            <li>Tempo: {features.classification?.tempo_category}</li>
          </ul>
        </div>

        <div className="feature-section">
          <h4>🌊 Spectral Features</h4>
          <ul>
            <li>Centroid (mean): {features.spectral_features?.centroid_mean?.toFixed(2)} Hz</li>
            <li>Bandwidth (mean): {features.spectral_features?.bandwidth_mean?.toFixed(2)} Hz</li>
            <li>Rolloff (mean): {features.spectral_features?.rolloff_mean?.toFixed(2)} Hz</li>
          </ul>
        </div>

        <div className="feature-section">
          <h4>⚡ Energy & Dynamics</h4>
          <ul>
            <li>RMS (mean): {features.energy_features?.rms_mean?.toFixed(4)}</li>
            <li>RMS (max): {features.energy_features?.rms_max?.toFixed(4)}</li>
            <li>Dynamic Range: {features.energy_features?.dynamic_range_db?.toFixed(2)} dB</li>
          </ul>
        </div>

        <div className="feature-section">
          <h4>⏱️ Temporal Features</h4>
          <ul>
            <li>ZCR (mean): {features.temporal_features?.zero_crossing_rate_mean?.toFixed(4)}</li>
            <li>Tempo: {features.temporal_features?.tempo_bpm?.toFixed(1)} BPM</li>
            <li>Beats: {features.temporal_features?.beat_count}</li>
          </ul>
        </div>

        <div className="feature-section">
          <h4>🎼 Harmonic/Percussive</h4>
          <ul>
            <li>Harmonic Ratio: {(features.harmonic_percussive?.harmonic_ratio * 100)?.toFixed(1)}%</li>
            <li>Percussive Ratio: {(features.harmonic_percussive?.percussive_ratio * 100)?.toFixed(1)}%</li>
          </ul>
        </div>
      </div>
    );
  };

  const renderVideoAnalysis = (analysis) => {
    if (!analysis) return <p>No video analysis available</p>;

    return (
      <div className="video-analysis">
        <div className="analysis-content">
          <h4>🎬 Gemini Analysis</h4>
          <p className="analysis-text">{analysis.analysis}</p>
        </div>
        
        {analysis.video_info && (
          <div className="video-info">
            <h4>📹 Video Info</h4>
            <ul>
              <li>Size: {analysis.video_info.file_size_mb?.toFixed(2)} MB</li>
              <li>Type: {analysis.video_info.mime_type}</li>
              <li>Model: {analysis.video_info.gemini_model}</li>
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="results-panel">
      <div className="results-header">
        <h2>📊 Analysis Results</h2>
        <button className="btn btn-secondary btn-sm" onClick={onRefresh}>
          🔄 Refresh
        </button>
      </div>

      {results.length === 0 ? (
        <div className="empty-state">
          <p>No results yet. Record and upload media to see analysis!</p>
        </div>
      ) : (
        <div className="results-list">
          {results.map((result) => (
            <div
              key={result.id}
              className={`result-item ${selectedResult?.id === result.id ? 'selected' : ''}`}
              onClick={() => setSelectedResult(result)}
            >
              <div className="result-header">
                <h3>{result.filename}</h3>
                <span className={`status-badge ${result.status}`}>
                  {result.status}
                </span>
              </div>
              <p className="result-timestamp">
                {formatTimestamp(result.upload_timestamp)}
              </p>
              <p className="result-type">Type: {result.media_type}</p>
            </div>
          ))}
        </div>
      )}

      {selectedResult && (
        <div className="result-details">
          <div className="details-header">
            <h3>{selectedResult.filename}</h3>
            <button
              className="btn-close"
              onClick={() => setSelectedResult(null)}
            >
              ✕
            </button>
          </div>

          {selectedResult.status === 'failed' && (
            <div className="error-message">
              <p>❌ Analysis failed: {selectedResult.error_message}</p>
            </div>
          )}

          {selectedResult.status === 'processing' && (
            <div className="processing-message">
              <div className="spinner"></div>
              <p>Processing in progress...</p>
            </div>
          )}

          {selectedResult.status === 'completed' && (
            <div className="details-content">
              {selectedResult.audio_features && (
                <div className="detail-section">
                  <button
                    className="section-toggle"
                    onClick={() => toggleSection('audio')}
                  >
                    <span>🎵 Audio Features</span>
                    <span>{expandedSection === 'audio' ? '▼' : '▶'}</span>
                  </button>
                  {expandedSection === 'audio' && (
                    <div className="section-content">
                      {renderAudioFeatures(selectedResult.audio_features)}
                    </div>
                  )}
                </div>
              )}

              {selectedResult.video_analysis && (
                <div className="detail-section">
                  <button
                    className="section-toggle"
                    onClick={() => toggleSection('video')}
                  >
                    <span>🎬 Video Analysis</span>
                    <span>{expandedSection === 'video' ? '▼' : '▶'}</span>
                  </button>
                  {expandedSection === 'video' && (
                    <div className="section-content">
                      {renderVideoAnalysis(selectedResult.video_analysis)}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ResultsPanel;
