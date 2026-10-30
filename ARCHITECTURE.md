# Architecture Overview

## Local Demo Architecture

This is a local version of an AWS serverless design by the author. It keeps the core functionality and runs on a single machine.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:5173)                  │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐  │
│  │ MediaRecorder│─▶│  FFmpeg.wasm   │─▶│  WebSocket Client │  │
│  │     API      │  │ (Audio Extract)│  │   (Real-time)     │  │
│  └──────────────┘  └────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST /api/upload
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│               FastAPI Server (localhost:8000)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     Upload Handler                        │  │
│  │  • Receives audio/video file                             │  │
│  │  • Creates analysis record in SQLite                     │  │
│  │  • Spawns background processing task                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Background Processing Task                   │  │
│  │                                                           │  │
│  │  ┌────────────────────┐    ┌─────────────────────────┐  │  │
│  │  │  Audio Processor   │    │   Video Analyzer        │  │  │
│  │  │                    │    │                         │  │  │
│  │  │  • librosa DSP     │    │  • Google Gemini API    │  │  │
│  │  │  • MFCCs           │    │  • Vision analysis      │  │  │
│  │  │  • Spectral        │    │  • Audio-visual sync    │  │  │
│  │  │  • Tempo/beats     │    │                         │  │  │
│  │  │  • Classification  │    │                         │  │  │
│  │  └────────────────────┘    └─────────────────────────┘  │  │
│  │           │                            │                  │  │
│  │           └────────────┬───────────────┘                  │  │
│  │                        ▼                                  │  │
│  │             ┌──────────────────────┐                     │  │
│  │             │   SQLite Database    │                     │  │
│  │             │  • Store results     │                     │  │
│  │             │  • Analysis history  │                     │  │
│  │             └──────────────────────┘                     │  │
│  │                        │                                  │  │
│  │                        ▼                                  │  │
│  │             ┌──────────────────────┐                     │  │
│  │             │  WebSocket Broadcast │                     │  │
│  │             │  • Real-time updates │                     │  │
│  │             └──────────────────────┘                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ WS /ws
                              ▼
                         Browser Updates

External API:
┌──────────────────────────┐
│  Google Gemini 2.0 Flash │
│  (Video Analysis)        │
└──────────────────────────┘
```

## Component Mapping: Production → Local

| Production Component | Local Equivalent | Notes |
|---------------------|------------------|-------|
| S3 Bucket | Local `uploads/` directory | Files stored on disk |
| EventBridge | FastAPI background tasks | Direct async processing |
| Step Functions | Sequential function calls | No orchestration layer needed |
| Lambda (Audio) | `audio_processor.py` | librosa-based DSP |
| Lambda (Video) | `video_analyzer.py` | Gemini API calls |
| DynamoDB | SQLite database | Relational storage |
| API Gateway | FastAPI routes | REST + WebSocket |
| CloudFront | Vite dev server | Local dev server |

## Key Technologies

### Frontend
- **React 18**: UI framework
- **Vite**: Build tool and dev server
- **MediaRecorder API**: Browser audio/video capture
- **FFmpeg.wasm**: Client-side audio extraction
- **WebSocket**: Real-time updates

### Backend
- **FastAPI**: Modern Python web framework
- **librosa**: Audio analysis and DSP
- **google-generativeai**: Gemini API client
- **aiosqlite**: Async SQLite database
- **websockets**: Real-time communication
- **uvicorn**: ASGI server

## Data Flow

### 1. Capture Phase
```
User clicks "Start Recording"
  → Browser requests mic/camera access
  → MediaRecorder starts capturing
  → User clicks "Stop Recording"
  → Blob created in browser memory
```

### 2. Processing Phase (Video)
```
Recorded video blob
  → FFmpeg.wasm extracts audio
  → Audio blob created
  → Upload to server
```

### 3. Upload Phase
```
FormData with audio/video file
  → POST /api/upload
  → File saved to uploads/
  → Record created in SQLite (status: processing)
  → WebSocket broadcast: "processing started"
  → Background task spawned
```

### 4. Analysis Phase
```
Background task:
  → Load audio file
  → Run librosa analysis (5-10 seconds)
    • Extract spectral features
    • Detect tempo/beats
    • Calculate MFCCs
    • Classify audio type
  → (If video) Upload to Gemini
  → Wait for Gemini processing
  → Generate analysis with custom prompt
  → Store results in SQLite
  → WebSocket broadcast: "analysis complete"
```

### 5. Display Phase
```
Browser receives WebSocket message
  → Update UI with results
  → Display audio features
  → Display Gemini analysis
  → Store in results list
```

## File Structure

```
audio-video-analyzer/
├── README.md                 # Main documentation
├── QUICKSTART.md            # Quick setup guide
├── .gitignore               # Git ignore rules
│
├── backend/
│   ├── server.py            # FastAPI application
│   ├── audio_processor.py   # librosa DSP analysis
│   ├── video_analyzer.py    # Gemini API integration
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Environment template
│   ├── .env                 # Your API keys (create this)
│   ├── analyzer.db          # SQLite database (auto-created)
│   └── uploads/             # Uploaded files (auto-created)
│
└── frontend/
    ├── package.json         # Node dependencies
    ├── vite.config.js       # Vite configuration
    ├── index.html           # HTML entry point
    └── src/
        ├── main.jsx         # React entry point
        ├── App.jsx          # Main app component
        ├── App.css          # Styles
        ├── MediaCapture.jsx # Recording interface
        └── ResultsPanel.jsx # Results display
```

## API Endpoints

### REST API
- `GET /` - API info
- `GET /api/health` - Health check
- `POST /api/upload` - Upload media for analysis
- `GET /api/results` - Get all results
- `GET /api/results/{id}` - Get specific result

### WebSocket
- `WS /ws` - Real-time updates channel

## Database Schema

```sql
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,              -- UUID
    filename TEXT NOT NULL,           -- Original filename
    media_type TEXT NOT NULL,         -- 'audio' or 'video'
    upload_timestamp TEXT NOT NULL,   -- ISO 8601 datetime
    audio_features TEXT,              -- JSON blob
    video_analysis TEXT,              -- JSON blob
    status TEXT NOT NULL,             -- 'processing', 'completed', 'failed'
    error_message TEXT                -- Error details if failed
);
```

## Extension Points

### Add New Audio Features
Edit `audio_processor.py`:
- Add new librosa feature extraction
- Modify classification logic
- Export additional metrics

### Customize Video Analysis
Edit `video_analyzer.py`:
- Modify Gemini prompts
- Add custom question templates
- Integrate additional analysis types

### Add New Processing Steps
Edit `server.py` → `process_media()`:
- Add preprocessing steps
- Chain multiple analyses
- Implement caching

### Deploy to AWS
The architecture is designed to map directly to AWS:
1. Replace SQLite with DynamoDB
2. Replace local storage with S3
3. Deploy FastAPI as Lambda + API Gateway
4. Add Step Functions for orchestration
5. Use EventBridge for S3 triggers

## Performance Considerations

### Audio Analysis (librosa)
- Typical processing: 5-10 seconds for 30-second audio
- CPU-bound operation
- Consider using lighter features for real-time

### Video Analysis (Gemini)
- Upload time: depends on file size
- Processing: 10-30 seconds typical
- API rate limits: monitor usage
- Cost: ~$0.075 per 1000 video tokens

### Optimizations
- Client-side audio extraction reduces upload size
- Async processing prevents blocking
- WebSocket reduces polling overhead
- SQLite adequate for local/small-scale use

## Security Notes

⚠️ **This is a demo/dev setup**. For production:
- Add authentication
- Validate file types/sizes
- Sanitize inputs
- Use environment-specific CORS
- Add rate limiting
- Encrypt sensitive data
- Use HTTPS/WSS
