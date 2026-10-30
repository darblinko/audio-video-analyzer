import React, { useEffect, useRef, useState } from 'react';
import { uploadRecording } from './api';
import { CaptureController } from './capture';
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
  const [isStarting, setIsStarting] = useState(false);
  const [recording, setRecording] = useState(null);
  const [busyMessage, setBusyMessage] = useState(null);

  const controllerRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    const controller = new CaptureController({
      getUserMedia: (constraints) => navigator.mediaDevices.getUserMedia(constraints),
      createRecorder: (stream, mimeType) =>
        new MediaRecorder(stream, mimeType ? { mimeType } : undefined),
    });
    controllerRef.current = controller;
    return () => controller.dispose();
  }, []);

  const clearPreview = () => {
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const startRecording = async () => {
    const type = mediaType;
    setIsStarting(true);
    try {
      const stream = await controllerRef.current.start(
        { audio: true, video: type === 'video' ? { facingMode: 'user' } : false },
        pickMimeType(type),
        (blob, mimeType) => {
          clearPreview();
          setIsRecording(false);
          setRecording({ blob, mediaType: type, mimeType });
        },
      );
      if (!stream) return;
      if (type === 'video' && videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsRecording(true);
    } catch (error) {
      clearPreview();
      onError(`Microphone or camera unavailable: ${error.message}`);
    } finally {
      setIsStarting(false);
    }
  };

  const stopRecording = () => controllerRef.current.stop();

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
            disabled={isRecording || isStarting || Boolean(busyMessage)}
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
          <button className="btn btn-primary" onClick={startRecording} disabled={isStarting}>
            {isStarting ? 'Waiting for permission' : 'Start recording'}
          </button>
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
