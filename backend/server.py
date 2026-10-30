"""
FastAPI server for audio/video analysis demo
"""
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import aiosqlite
import os
import json
import uuid
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import asyncio
from dotenv import load_dotenv

from audio_processor import AudioProcessor
from video_analyzer import VideoAnalyzer

# Load environment variables
load_dotenv()

# Create necessary directories
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

DB_PATH = "analyzer.db"

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Initialize processors
audio_processor = AudioProcessor()
try:
    video_analyzer = VideoAnalyzer()
    GEMINI_ENABLED = True
except Exception as e:
    print(f"Warning: Gemini API not configured: {e}")
    print("Video analysis will be disabled. Set GOOGLE_API_KEY in .env file.")
    GEMINI_ENABLED = False
    video_analyzer = None

# Database initialization
async def init_db():
    """Initialize SQLite database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL,
                audio_features TEXT,
                video_analysis TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """)
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    await init_db()
    print("✓ Database initialized")
    print("✓ Upload directory ready")
    print(f"✓ Gemini API: {'Enabled' if GEMINI_ENABLED else 'Disabled'}")
    yield
    print("Shutting down...")

# FastAPI app
app = FastAPI(title="Audio/Video Analyzer API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Audio/Video Analyzer API",
        "version": "1.0.0",
        "gemini_enabled": GEMINI_ENABLED,
        "endpoints": {
            "upload": "POST /api/upload",
            "results": "GET /api/results",
            "websocket": "WS /ws"
        }
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "gemini_enabled": GEMINI_ENABLED,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/upload")
async def upload_media(
    file: UploadFile = File(...),
    media_type: str = "audio"  # "audio" or "video"
):
    """
    Upload audio or video file for analysis
    """
    analysis_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    try:
        # Save uploaded file
        file_extension = Path(file.filename).suffix
        file_path = UPLOAD_DIR / f"{analysis_id}{file_extension}"
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Insert initial record
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO analyses 
                (id, filename, media_type, upload_timestamp, status) 
                VALUES (?, ?, ?, ?, ?)""",
                (analysis_id, file.filename, media_type, timestamp, "processing")
            )
            await db.commit()
        
        # Broadcast status update
        await manager.broadcast({
            "type": "status_update",
            "analysis_id": analysis_id,
            "status": "processing",
            "message": "File uploaded, starting analysis..."
        })
        
        # Process in background
        asyncio.create_task(process_media(analysis_id, str(file_path), media_type, file.filename))
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "message": "File uploaded successfully, processing started"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": "Failed to upload file"
            }
        )

async def process_media(analysis_id: str, file_path: str, media_type: str, filename: str):
    """
    Background task to process audio/video
    """
    try:
        audio_features = None
        video_analysis = None
        
        # Step 1: Audio analysis
        await manager.broadcast({
            "type": "progress",
            "analysis_id": analysis_id,
            "step": "audio_analysis",
            "message": "Analyzing audio features..."
        })
        
        audio_result = audio_processor.analyze_audio(file_path)
        if audio_result["success"]:
            audio_features = audio_result["features"]
        
        # Step 2: Video analysis (if video and Gemini enabled)
        if media_type == "video" and GEMINI_ENABLED:
            await manager.broadcast({
                "type": "progress",
                "analysis_id": analysis_id,
                "step": "video_analysis",
                "message": "Analyzing video with Gemini..."
            })
            
            # Use audio-visual sync analysis if audio features available
            if audio_features:
                video_result = video_analyzer.analyze_video_audio_sync(
                    file_path, 
                    {"classification": audio_features.get("classification", {}),
                     "basic_info": audio_features.get("basic_info", {}),
                     "temporal_features": audio_features.get("temporal_features", {})}
                )
            else:
                video_result = video_analyzer.analyze_video(file_path)
            
            if video_result["success"]:
                video_analysis = {
                    "analysis": video_result.get("analysis", ""),
                    "video_info": video_result.get("video_info", {})
                }
        
        # Update database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE analyses 
                SET audio_features = ?, video_analysis = ?, status = ? 
                WHERE id = ?""",
                (
                    json.dumps(audio_features) if audio_features else None,
                    json.dumps(video_analysis) if video_analysis else None,
                    "completed",
                    analysis_id
                )
            )
            await db.commit()
        
        # Broadcast completion
        await manager.broadcast({
            "type": "analysis_complete",
            "analysis_id": analysis_id,
            "status": "completed",
            "audio_features": audio_features,
            "video_analysis": video_analysis,
            "message": "Analysis completed successfully"
        })
        
    except Exception as e:
        # Update database with error
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE analyses 
                SET status = ?, error_message = ? 
                WHERE id = ?""",
                ("failed", str(e), analysis_id)
            )
            await db.commit()
        
        # Broadcast error
        await manager.broadcast({
            "type": "analysis_error",
            "analysis_id": analysis_id,
            "status": "failed",
            "error": str(e),
            "message": "Analysis failed"
        })
    
    finally:
        # Optionally clean up file after processing
        # os.remove(file_path)
        pass

@app.get("/api/results")
async def get_all_results():
    """Get all analysis results"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM analyses ORDER BY upload_timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                
                results = []
                for row in rows:
                    result = dict(row)
                    # Parse JSON fields
                    if result["audio_features"]:
                        result["audio_features"] = json.loads(result["audio_features"])
                    if result["video_analysis"]:
                        result["video_analysis"] = json.loads(result["video_analysis"])
                    results.append(result)
                
                return {
                    "success": True,
                    "count": len(results),
                    "results": results
                }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.get("/api/results/{analysis_id}")
async def get_result(analysis_id: str):
    """Get specific analysis result"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    raise HTTPException(status_code=404, detail="Analysis not found")
                
                result = dict(row)
                # Parse JSON fields
                if result["audio_features"]:
                    result["audio_features"] = json.loads(result["audio_features"])
                if result["video_analysis"]:
                    result["video_analysis"] = json.loads(result["video_analysis"])
                
                return {
                    "success": True,
                    "result": result
                }
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for testing
            await websocket.send_json({
                "type": "echo",
                "message": f"Received: {data}"
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    print("Starting Audio/Video Analyzer API Server...")
    print("Server will be available at http://localhost:8000")
    print("WebSocket endpoint: ws://localhost:8000/ws")
    uvicorn.run(app, host="0.0.0.0", port=8000)
