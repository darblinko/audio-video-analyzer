// All requests use relative URLs so the Vite dev proxy forwards them to the API server.

async function request(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return body;
}

export const getHealth = () => request('/api/health');
export const getResults = () => request('/api/results');
export const getSamples = () => request('/api/samples');

export const analyzeSample = (sampleId) =>
  request(`/api/samples/${encodeURIComponent(sampleId)}/analyze`, { method: 'POST' });

export function uploadRecording({ audioWav, videoBlob, videoName }) {
  const form = new FormData();
  form.append('audio', audioWav, 'audio.wav');
  form.append('media_type', videoBlob ? 'video' : 'audio');
  if (videoBlob) {
    form.append('video', videoBlob, videoName);
  }
  return request('/api/upload', { method: 'POST', body: form });
}

export function websocketUrl() {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${window.location.host}/ws`;
}
