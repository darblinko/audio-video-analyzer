// Run with: npm test (node --test). The WAV bytes are parsed here independently of wav.js.
import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { blobToWav, encodeWav } from './wav.js';

function ascii(view, offset, length) {
  return String.fromCharCode(...new Uint8Array(view.buffer, offset, length));
}

async function parseWav(blob) {
  const view = new DataView(await blob.arrayBuffer());
  const dataBytes = view.getUint32(40, true);
  const samples = [];
  for (let offset = 44; offset < 44 + dataBytes; offset += 2) {
    samples.push(view.getInt16(offset, true));
  }
  return {
    riff: ascii(view, 0, 4),
    riffSize: view.getUint32(4, true),
    wave: ascii(view, 8, 4),
    fmt: ascii(view, 12, 4),
    fmtSize: view.getUint32(16, true),
    format: view.getUint16(20, true),
    channels: view.getUint16(22, true),
    sampleRate: view.getUint32(24, true),
    byteRate: view.getUint32(28, true),
    blockAlign: view.getUint16(32, true),
    bitsPerSample: view.getUint16(34, true),
    data: ascii(view, 36, 4),
    dataBytes,
    totalBytes: view.byteLength,
    samples,
  };
}

const realAudioContext = globalThis.AudioContext;
afterEach(() => {
  globalThis.AudioContext = realAudioContext;
});

test('encodeWav writes a 16-bit mono PCM header', async () => {
  const wav = await parseWav(encodeWav(new Float32Array(10), 16000));
  assert.equal(wav.riff, 'RIFF');
  assert.equal(wav.wave, 'WAVE');
  assert.equal(wav.fmt, 'fmt ');
  assert.equal(wav.data, 'data');
  assert.equal(wav.fmtSize, 16);
  assert.equal(wav.format, 1);
  assert.equal(wav.channels, 1);
  assert.equal(wav.sampleRate, 16000);
  assert.equal(wav.byteRate, 32000);
  assert.equal(wav.blockAlign, 2);
  assert.equal(wav.bitsPerSample, 16);
  assert.equal(wav.dataBytes, 20);
  assert.equal(wav.riffSize, 36 + 20);
  assert.equal(wav.totalBytes, 44 + 20);
});

test('encodeWav scales samples to int16 and clips out-of-range values', async () => {
  const blob = encodeWav(new Float32Array([0, 0.5, -0.5, 1, -1, 2, -2]), 22050);
  assert.equal(blob.type, 'audio/wav');
  const { samples } = await parseWav(blob);
  assert.deepEqual(samples, [0, 16384, -16383, 32767, -32767, 32767, -32767]);
});

test('blobToWav averages channels, keeps the sample rate and closes the context', async () => {
  let closed = false;
  globalThis.AudioContext = class {
    async decodeAudioData(bytes) {
      assert.equal(bytes.byteLength, 3);
      const channels = [new Float32Array([0.5, 1, -1]), new Float32Array([0.5, 0, 0])];
      return {
        length: 3,
        numberOfChannels: 2,
        sampleRate: 48000,
        getChannelData: (index) => channels[index],
      };
    }

    async close() {
      closed = true;
    }
  };
  const wav = await parseWav(await blobToWav(new Blob([new Uint8Array(3)])));
  assert.equal(wav.sampleRate, 48000);
  assert.deepEqual(wav.samples, [16384, 16384, -16383]);
  assert.equal(closed, true);
});
