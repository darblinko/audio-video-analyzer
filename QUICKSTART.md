# 🚀 Quickstart Guide

Get the Audio/Video Analyzer demo running in 5 minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.9+)
python --version

# Check Node.js version (need 18+)
node --version

# Check npm
npm --version
```

If you don't have these installed:
- Python: https://www.python.org/downloads/
- Node.js: https://nodejs.org/

## Step 1: Get Your Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy your key

## Step 2: Backend Setup (Terminal 1)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your Gemini API key
# On macOS/Linux:
nano .env
# On Windows:
notepad .env

# Add this line (replace with your actual key):
# GOOGLE_API_KEY=your_actual_api_key_here

# Start the server
python server.py
```

You should see:
```
✓ Database initialized
✓ Upload directory ready
✓ Gemini API: Enabled
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Frontend Setup (Terminal 2)

Open a NEW terminal window:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

You should see:
```
VITE v5.x.x ready in xxx ms
➜ Local: http://localhost:5173/
```

## Step 4: Open and Test

1. Open your browser to: **http://localhost:5173**
2. Grant microphone/camera permissions when prompted
3. Choose "Audio Only" or "Video"
4. Click "Start Recording"
5. Speak or record for a few seconds
6. Click "Stop Recording"
7. Click "Upload & Analyze"
8. Watch real-time analysis appear!

## Troubleshooting

### "FFmpeg not loaded" warning
- This is normal - FFmpeg.wasm loads in the background
- Wait a few seconds and try again
- Audio extraction will work once loaded

### "GOOGLE_API_KEY not found"
- Make sure you created `.env` file in `backend/` directory
- Check that your API key is valid
- Restart the backend server after adding the key

### "Failed to access microphone/camera"
- Grant permissions in your browser
- Try using Chrome or Edge (better WebRTC support)
- On macOS: Check System Preferences > Security & Privacy > Microphone/Camera

### Port already in use
- Backend (8000): Kill any process using port 8000
- Frontend (5173): Kill any process using port 5173

```bash
# On macOS/Linux:
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# On Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## What You'll See

### Audio Analysis
- Duration, sample rate, channels
- Audio type classification (musical, speech, noise)
- Spectral features (frequency analysis)
- Energy and dynamics
- Tempo detection
- Harmonic/percussive separation

### Video Analysis (via Gemini)
- Scene description
- Object detection
- Action recognition
- Mood/atmosphere analysis
- Audio-visual synchronization

## Next Steps

- Experiment with different audio types (music, speech, ambient)
- Try recording videos with different content
- Check the SQLite database (`backend/analyzer.db`) for stored results
- Modify the Gemini prompts in `video_analyzer.py` for custom analysis
- Add your own DSP features in `audio_processor.py`

## Need Help?

- Check the main README.md for detailed documentation
- Review the API endpoints at http://localhost:8000/docs (FastAPI auto-docs)
- Inspect browser console for frontend errors
- Check terminal output for backend errors

Happy analyzing! 🎵🎬
