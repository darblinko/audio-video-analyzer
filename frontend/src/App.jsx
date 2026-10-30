import React, { useCallback, useEffect, useState } from 'react';
import MediaCapture from './MediaCapture';
import ResultsPanel from './ResultsPanel';
import SamplePicker from './SamplePicker';
import { getHealth, getResults, websocketUrl } from './api';
import './App.css';

const RECONNECT_MS = 3000;

function useAnalysisSocket(onMessage) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let socket = null;
    let timer = null;
    let stopped = false;

    const connect = () => {
      socket = new WebSocket(websocketUrl());
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event) => onMessage(JSON.parse(event.data));
      socket.onclose = () => {
        setConnected(false);
        if (!stopped) timer = setTimeout(connect, RECONNECT_MS);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      if (!socket) return;
      socket.onmessage = null;
      socket.onclose = null;
      if (socket.readyState === WebSocket.CONNECTING) {
        // Closing a socket that is still connecting logs a browser warning; close it on open.
        socket.onopen = () => socket.close();
      } else {
        socket.close();
      }
    };
  }, [onMessage]);

  return connected;
}

function GeminiBadge({ gemini }) {
  if (!gemini) return null;
  return (
    <div className={`gemini-badge ${gemini.enabled ? 'on' : 'off'}`}>
      {gemini.enabled ? `Gemini: ${gemini.model}` : 'Gemini: off (no GOOGLE_API_KEY)'}
    </div>
  );
}

function App() {
  const [results, setResults] = useState([]);
  const [current, setCurrent] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [gemini, setGemini] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setResults((await getResults()).results);
    } catch (err) {
      setError(`Could not load results: ${err.message}`);
    }
  }, []);

  const handleMessage = useCallback((message) => {
    setCurrent(message);
    if (message.type === 'analysis_complete' || message.type === 'analysis_error') {
      setSelectedId(message.analysis_id);
      refresh();
    }
  }, [refresh]);

  const connected = useAnalysisSocket(handleMessage);

  useEffect(() => {
    refresh();
    getHealth()
      .then((body) => setGemini(body.gemini))
      .catch((err) => setError(`API server unreachable: ${err.message}`));
  }, [refresh]);

  const handleStarted = useCallback((analysisId) => {
    setError(null);
    setCurrent({ analysis_id: analysisId, status: 'processing', message: 'Queued' });
    refresh();
  }, [refresh]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Audio/Video Analyzer</h1>
        <p className="subtitle">librosa audio features and optional Gemini video description</p>
        <div className="header-badges">
          <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            {connected ? 'WebSocket connected' : 'Connecting'}
          </div>
          <GeminiBadge gemini={gemini} />
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <p>{error}</p>
          <button className="btn-close" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <main className="app-main">
        <div className="capture-section">
          <SamplePicker onUploadComplete={handleStarted} onError={setError} />
          <MediaCapture onUploadComplete={handleStarted} onError={setError} />
          {current && (
            <div className="current-analysis">
              <h3>Current run</h3>
              <div className="analysis-status">
                <span className={`status-badge ${current.status || 'processing'}`}>
                  {current.status || current.step || 'processing'}
                </span>
                <p>{current.message}</p>
              </div>
            </div>
          )}
        </div>
        <div className="results-section">
          <ResultsPanel
            results={results}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRefresh={refresh}
          />
        </div>
      </main>
    </div>
  );
}

export default App;
