// One recording at a time. Each recording owns its stream and chunks, and every stream that
// getUserMedia returns is stopped, including one that arrives after a cancel or an error.

export function stopTracks(stream) {
  stream?.getTracks().forEach((track) => track.stop());
}

export class CaptureController {
  constructor({ getUserMedia, createRecorder }) {
    this.getUserMedia = getUserMedia;
    this.createRecorder = createRecorder;
    this.state = 'idle';
    this.stream = null;
    this.recorder = null;
    this.disposed = false;
  }

  // Resolves to the recording stream, or to null when a start is already pending or active,
  // or when the controller was disposed while permission was pending.
  async start(constraints, mimeType, onRecorded) {
    if (this.state !== 'idle' || this.disposed) return null;
    this.state = 'starting';
    let stream = null;
    try {
      stream = await this.getUserMedia(constraints);
      if (this.disposed) {
        stopTracks(stream);
        return null;
      }
      const recorder = this.createRecorder(stream, mimeType);
      const chunks = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        stopTracks(stream);
        if (this.recorder === recorder) {
          this.recorder = null;
          this.stream = null;
          this.state = 'idle';
        }
        if (!this.disposed) onRecorded(new Blob(chunks, { type: recorder.mimeType }), recorder.mimeType);
      };
      recorder.start();
      this.stream = stream;
      this.recorder = recorder;
      this.state = 'recording';
      return stream;
    } catch (error) {
      stopTracks(stream);
      throw error;
    } finally {
      if (this.state === 'starting') this.state = 'idle';
    }
  }

  stop() {
    if (this.state === 'recording' && this.recorder.state !== 'inactive') this.recorder.stop();
  }

  dispose() {
    this.disposed = true;
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
    stopTracks(this.stream);
    this.stream = null;
  }
}
