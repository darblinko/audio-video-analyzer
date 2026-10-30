import React, { useEffect, useRef, useState } from 'react';
import { uploadRecording } from './api';
import { blobToWav } from './wav';

const MIME_CANDIDATES = {
  audio: ['audio/webm;codecs=opus', 'audio/mp4'],
  video: ['video/webm;codecs=vp8,opus', 'video/mp4'],
};

function pickMimeType(mediaType) {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return '';
  return MIME_CANDIDATES[mediaType].find((type) => MediaRecorder.isTypeSupported(type)) || '';
}

function videoFileName(mimeType) {
  return `recording_${Date.now()}.${mimeType.includes('mp4') ? 'mp4' : 'webm'}`;
}

function MediaCapture({ onUploadComplete, onError }) {
  const [mediaType, setMediaType] = useState('audio');
  const [isRecording, setIsRecording] = useState(false);
  const [recording, setRecording] = useState(null);
  const [busyMessage, setBusyMessage] = useState(null);

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const videoRef = useRef(null);
  const chunksRef = useRef([]);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  useEffect(() => stopStream, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: mediaType === 'video' ? { facingMode: 'user' } : false,
      });
      streamRef.current = stream;
      if (mediaType === 'video' && videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      const mimeType = pickMimeType(mediaType);
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        setRecording({ blob, mediaType, mimeType: recorder.mimeType });
        stopStream();
      };
      recorder.start();
      recorderRef.current = recorder;
      setIsRecording(true);
    } catch (error) {
      stopStream();
      onError(`Microphone or camera unavailable: ${error.message}`);
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && isRecording) {
      recorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const upload = async () => {
    if (!recording) return;
    try {
      setBusyMessage('Converting the audio track to WAV');
      const audioWav = await blobToWav(recording.blob);
      setBusyMessage('Uploading');
      const isVideo = recording.mediaType === 'video';
      const result = await uploadRecording({
        audioWav,
        videoBlob: isVideo ? recording.blob : null,
        videoName: isVideo ? videoFileName(recording.mimeType) : null,
      });
      onUploadComplete(result.analysis_id);
      setRecording(null);
    } catch (error) {
      onError(`Upload failed: ${error.message}`);
    } finally {
      setBusyMessage(null);
    }
  };

  return (
    <div className="media-capture">
      <h2>Record</h2>
      <div className="media-type-selector">
        {['audio', 'video'].map((type) => (
          <button
            key={type}
            className={`type-btn ${mediaType === type ? 'active' : ''}`}
            onClick={() => setMediaType(type)}
            disabled={isRecording || Boolean(busyMessage)}
          >
            {type === 'audio' ? 'Audio only' : 'Video and audio'}
          </button>
        ))}
      </div>

      {mediaType === 'video' && (
        <div className="video-preview">
          <video ref={videoRef} autoPlay playsInline muted />
        </div>
      )}

      <div className="recording-controls">
        {!isRecording && !recording && !busyMessage && (
          <button className="btn btn-primary" onClick={startRecording}>Start recording</button>
        )}
        {isRecording && (
          <button className="btn btn-danger" onClick={stopRecording}>Stop recording</button>
        )}
        {recording && !busyMessage && (
          <div className="recorded-actions">
            <button className="btn btn-success" onClick={upload}>Upload and analyze</button>
            <button className="btn btn-secondary" onClick={() => setRecording(null)}>Discard</button>
          </div>
        )}
        {busyMessage && (
          <div className="processing-status">
            <div className="spinner"></div>
            <p>{busyMessage}</p>
          </div>
        )}
      </div>

      <p className="info-text">
        {mediaType === 'audio'
          ? 'Records the microphone. The audio is analyzed on this machine.'
          : 'Records the front camera and microphone. With GOOGLE_API_KEY set, the video is uploaded to the Google Gemini API.'}
      </p>
    </div>
  );
}

export default MediaCapture;
