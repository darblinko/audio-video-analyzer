import React, { useState, useEffect } from 'react';
import MediaCapture from './MediaCapture';
import ResultsPanel from './ResultsPanel';
import './App.css';

function App() {
  const [results, setResults] = useState([]);
  const [ws, setWs] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [currentAnalysis, setCurrentAnalysis] = useState(null);

  // Initialize WebSocket connection
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    const websocket = new WebSocket('ws://localhost:8000/ws');
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('WebSocket message:', data);
      
      if (data.type === 'analysis_complete') {
        setCurrentAnalysis(data);
        fetchResults(); // Refresh results list
      } else if (data.type === 'progress' || data.type === 'status_update') {
        setCurrentAnalysis(data);
      } else if (data.type === 'analysis_error') {
        setCurrentAnalysis(data);
        alert(`Analysis failed: ${data.error}`);
      }
    };
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
      // Attempt to reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };
    
    setWs(websocket);
  };

  const fetchResults = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/results');
      const data = await response.json();
      if (data.success) {
        setResults(data.results);
      }
    } catch (error) {
      console.error('Failed to fetch results:', error);
    }
  };

  useEffect(() => {
    fetchResults();
  }, []);

  const handleUploadComplete = (analysisId) => {
    console.log('Upload complete:', analysisId);
    setCurrentAnalysis({
      type: 'status_update',
      analysis_id: analysisId,
      status: 'processing',
      message: 'Processing started...'
    });
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🎙️ Audio/Video Analyzer</h1>
        <p className="subtitle">Capture, analyze, and understand your media with AI</p>
        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-dot"></span>
          {connectionStatus === 'connected' ? 'Live' : 'Connecting...'}
        </div>
      </header>

      <main className="app-main">
        <div className="capture-section">
          <MediaCapture onUploadComplete={handleUploadComplete} />
          
          {currentAnalysis && (
            <div className="current-analysis">
              <h3>Current Analysis</h3>
              <div className="analysis-status">
                <span className="status-badge">{currentAnalysis.status || 'processing'}</span>
                <p>{currentAnalysis.message}</p>
              </div>
            </div>
          )}
        </div>

        <div className="results-section">
          <ResultsPanel results={results} onRefresh={fetchResults} />
        </div>
      </main>
    </div>
  );
}

export default App;
