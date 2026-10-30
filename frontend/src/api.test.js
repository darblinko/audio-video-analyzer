// Run with: npm test (node --test). fetch is replaced by a stub that records the request.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { uploadRecording } from './api.js';

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function stubFetch(status, body) {
  const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    return new Response(JSON.stringify(body), { status, statusText: 'Status' });
  };
  return calls;
}

test('uploadRecording sends the WAV and the original video as multipart parts', async () => {
  const calls = stubFetch(202, { analysis_id: 'abc', status: 'processing' });
  const audioWav = new Blob(['RIFF'], { type: 'audio/wav' });
  const videoBlob = new Blob(['webm'], { type: 'video/webm' });
  const result = await uploadRecording({ audioWav, videoBlob, videoName: 'recording_1.webm' });

  assert.deepEqual(result, { analysis_id: 'abc', status: 'processing' });
  const [{ path, options }] = calls;
  assert.equal(path, '/api/upload');
  assert.equal(options.method, 'POST');
  const form = options.body;
  assert.deepEqual([...form.keys()], ['audio', 'media_type', 'video']);
  assert.equal(form.get('audio').name, 'audio.wav');
  assert.equal(await form.get('audio').text(), 'RIFF');
  assert.equal(form.get('media_type'), 'video');
  assert.equal(form.get('video').name, 'recording_1.webm');
  assert.equal(await form.get('video').text(), 'webm');
});

test('uploadRecording sends audio only when there is no video', async () => {
  const calls = stubFetch(202, { analysis_id: 'abc' });
  await uploadRecording({ audioWav: new Blob(['RIFF']), videoBlob: null, videoName: null });
  const form = calls[0].options.body;
  assert.deepEqual([...form.keys()], ['audio', 'media_type']);
  assert.equal(form.get('media_type'), 'audio');
});

test('a rejected upload raises an error with the server detail', async () => {
  stubFetch(413, { detail: 'upload exceeds AVA_MAX_UPLOAD_MB' });
  await assert.rejects(
    uploadRecording({ audioWav: new Blob(['RIFF']), videoBlob: null, videoName: null }),
    /413 upload exceeds AVA_MAX_UPLOAD_MB/,
  );
});
