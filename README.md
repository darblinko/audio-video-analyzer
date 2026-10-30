# Audio/Video Analyzer - Local Demo

A local demo for capturing audio/video from browser, extracting audio, performing DSP analysis, and analyzing with Google Gemini API.

## Architecture (Local Version)

```
Browser → FastAPI Server → SQLite
   ↓            ↓
MediaRecorder   ├→ librosa (Audio DSP)
FFmpeg.wasm     └→ Gemini API (Video Analysis)
```

## Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend dev server)
- Google AI Studio API Key for Gemini

## Setup

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

### 3. Environment Variables

Create `backend/.env`:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```

Get your API key from: https://aistudio.google.com/app/apikey

## Running the Demo

### Terminal 1 - Backend Server
```bash
cd backend
source venv/bin/activate
python server.py
```
Server runs on http://localhost:8000

### Terminal 2 - Frontend Dev Server
```bash
cd frontend
npm run dev
```
Frontend runs on http://localhost:5173

## Usage

1. Open http://localhost:5173 in your browser
2. Grant microphone/camera permissions
3. Choose:
   - **Audio Only**: Records from microphone
   - **Video**: Records from camera (audio extracted automatically)
4. Click Start Recording → Stop Recording
5. View real-time analysis results:
   - Audio DSP metrics (duration, sample rate, spectral features)
   - Gemini video analysis (if video captured)
6. Results saved to SQLite database

## Project Structure

```
audio-video-analyzer/
├── backend/
│   ├── server.py           # FastAPI server
│   ├── audio_processor.py  # librosa DSP analysis
│   ├── video_analyzer.py   # Gemini API integration
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   ├── MediaCapture.jsx
│   │   └── ResultsPanel.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Features

- ✅ Browser audio/video capture (MediaRecorder API)
- ✅ Client-side audio extraction from video (FFmpeg.wasm)
- ✅ Audio DSP analysis (librosa: MFCCs, spectral features, tempo)
- ✅ Video analysis via Gemini 2.0 Flash API
- ✅ WebSocket real-time updates
- ✅ SQLite storage for results
- ✅ Mobile browser support

## API Endpoints

- `POST /api/upload` - Upload audio/video for analysis
- `GET /api/results` - Get all analysis results
- `GET /api/results/{id}` - Get specific result
- `WS /ws` - WebSocket for real-time updates

## Notes

- Audio format: WebM/Opus (auto-converts for iOS)
- Video format: WebM/VP8 or MP4/H264
- Max file size: 50MB (configurable)
- Results retained in SQLite: `backend/analyzer.db`
