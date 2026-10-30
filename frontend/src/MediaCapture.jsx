import React, { useState, useRef, useEffect } from 'react';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile, toBlobURL } from '@ffmpeg/util';

function MediaCapture({ onUploadComplete }) {
  const [mediaType, setMediaType] = useState('audio'); // 'audio' or 'video'
  const [isRecording, setIsRecording] = useState(false);
  const [mediaStream, setMediaStream] = useState(null);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [ffmpegLoaded, setFfmpegLoaded] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const videoRef = useRef(null);
  const chunksRef = useRef([]);
  const ffmpegRef = useRef(new FFmpeg());

  // Load FFmpeg.wasm
  useEffect(() => {
    loadFFmpeg();
  }, []);

  const loadFFmpeg = async () => {
    try {
      const ffmpeg = ffmpegRef.current;
      const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd';
      
      await ffmpeg.load({
        coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
        wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
      });
      
      setFfmpegLoaded(true);
      console.log('FFmpeg loaded successfully');
    } catch (error) {
      console.error('Failed to load FFmpeg:', error);
      alert('Failed to load FFmpeg. Audio extraction from video will not work.');
    }
  };

  const startRecording = async () => {
    try {
      const constraints = {
        audio: true,
        video: mediaType === 'video' ? { facingMode: 'user' } : false
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      setMediaStream(stream);

      // Show video preview
      if (mediaType === 'video' && videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }

      // Setup MediaRecorder
      const options = { mimeType: 'video/webm;codecs=vp8,opus' };
      let mediaRecorder;
      
      try {
        mediaRecorder = new MediaRecorder(stream, options);
      } catch (e) {
        // Fallback for browsers that don't support webm
        mediaRecorder = new MediaRecorder(stream);
      }

      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        setRecordedBlob(blob);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
        setMediaStream(null);
        
        if (videoRef.current) {
          videoRef.current.srcObject = null;
        }
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Failed to access microphone/camera. Please grant permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const extractAudioFromVideo = async (videoBlob) => {
    if (!ffmpegLoaded) {
      console.log('FFmpeg not loaded, skipping audio extraction');
      return videoBlob;
    }

    try {
      setIsProcessing(true);
      const ffmpeg = ffmpegRef.current;

      // Write video to FFmpeg filesystem
      await ffmpeg.writeFile('input.webm', await fetchFile(videoBlob));

      // Extract audio
      await ffmpeg.exec(['-i', 'input.webm', '-vn', '-acodec', 'libmp3lame', 'output.mp3']);

      // Read extracted audio
      const data = await ffmpeg.readFile('output.mp3');
      const audioBlob = new Blob([data.buffer], { type: 'audio/mp3' });

      setIsProcessing(false);
      return audioBlob;
    } catch (error) {
      console.error('Audio extraction failed:', error);
      setIsProcessing(false);
      // Return original video if extraction fails
      return videoBlob;
    }
  };

  const uploadMedia = async () => {
    if (!recordedBlob) return;

    try {
      setIsProcessing(true);
      setUploadProgress('Preparing file...');

      let uploadBlob = recordedBlob;
      let uploadMediaType = mediaType;

      // If video, extract audio first
      if (mediaType === 'video' && ffmpegLoaded) {
        setUploadProgress('Extracting audio from video...');
        uploadBlob = await extractAudioFromVideo(recordedBlob);
        uploadMediaType = 'audio';
      }

      // Upload to server
      setUploadProgress('Uploading to server...');
      const formData = new FormData();
      const filename = `recording_${Date.now()}.${mediaType === 'video' ? 'webm' : 'mp3'}`;
      formData.append('file', uploadBlob, filename);
      formData.append('media_type', uploadMediaType);

      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (result.success) {
        setUploadProgress('Analysis started!');
        onUploadComplete(result.analysis_id);
        
        // Clear recorded blob after successful upload
        setTimeout(() => {
          setRecordedBlob(null);
          setUploadProgress(null);
        }, 2000);
      } else {
        throw new Error(result.message || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload failed:', error);
      alert(`Upload failed: ${error.message}`);
      setUploadProgress(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const resetRecording = () => {
    setRecordedBlob(null);
    setUploadProgress(null);
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      setMediaStream(null);
    }
  };

  return (
    <div className="media-capture">
      <h2>📹 Capture Media</h2>
      
      <div className="media-type-selector">
        <button
          className={`type-btn ${mediaType === 'audio' ? 'active' : ''}`}
          onClick={() => setMediaType('audio')}
          disabled={isRecording}
        >
          🎙️ Audio Only
        </button>
        <button
          className={`type-btn ${mediaType === 'video' ? 'active' : ''}`}
          onClick={() => setMediaType('video')}
          disabled={isRecording}
        >
          🎥 Video
        </button>
      </div>

      {mediaType === 'video' && (
        <div className="video-preview">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', maxWidth: '500px', borderRadius: '8px' }}
          />
        </div>
      )}

      <div className="recording-controls">
        {!isRecording && !recordedBlob && (
          <button className="btn btn-primary" onClick={startRecording}>
            ⏺️ Start Recording
          </button>
        )}

        {isRecording && (
          <button className="btn btn-danger" onClick={stopRecording}>
            ⏹️ Stop Recording
          </button>
        )}

        {recordedBlob && !isProcessing && (
          <div className="recorded-actions">
            <button className="btn btn-success" onClick={uploadMedia}>
              ⬆️ Upload & Analyze
            </button>
            <button className="btn btn-secondary" onClick={resetRecording}>
              🔄 Record Again
            </button>
          </div>
        )}

        {isProcessing && (
          <div className="processing-status">
            <div className="spinner"></div>
            <p>{uploadProgress || 'Processing...'}</p>
          </div>
        )}
      </div>

      <div className="info-section">
        <p className="info-text">
          {mediaType === 'audio' 
            ? '🎤 Click "Start Recording" to capture audio from your microphone'
            : '📹 Click "Start Recording" to capture video with audio from your camera'}
        </p>
        {!ffmpegLoaded && mediaType === 'video' && (
          <p className="warning-text">⚠️ FFmpeg loading... Audio extraction may not work yet.</p>
        )}
      </div>
    </div>
  );
}

export default MediaCapture;
