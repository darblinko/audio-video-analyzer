// Run with: npm test (node --test). getUserMedia and MediaRecorder are fakes.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CaptureController } from './capture.js';

class FakeStream {
  constructor() {
    this.tracks = [{ stopped: false }, { stopped: false }];
    for (const track of this.tracks) track.stop = () => { track.stopped = true; };
  }

  getTracks() {
    return this.tracks;
  }

  get stopped() {
    return this.tracks.every((track) => track.stopped);
  }
}

class FakeRecorder {
  constructor(stream, mimeType) {
    this.stream = stream;
    this.mimeType = mimeType || 'audio/webm';
    this.state = 'inactive';
  }

  start() {
    this.state = 'recording';
  }

  stop() {
    this.ondataavailable({ data: new Blob(['chunk']) });
    this.state = 'inactive';
    this.onstop();
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function controllerWith(getUserMedia, createRecorder = (stream, type) => new FakeRecorder(stream, type)) {
  return new CaptureController({ getUserMedia, createRecorder });
}

const CONSTRAINTS = { audio: true, video: false };

test('a second start while permission is pending is ignored', async () => {
  const pending = deferred();
  let requests = 0;
  const controller = controllerWith(() => { requests += 1; return pending.promise; });
  const first = controller.start(CONSTRAINTS, '', () => {});
  assert.equal(await controller.start(CONSTRAINTS, '', () => {}), null);
  const stream = new FakeStream();
  pending.resolve(stream);
  assert.equal(await first, stream);
  assert.equal(requests, 1);
  assert.equal(await controller.start(CONSTRAINTS, '', () => {}), null);
});

test('stop delivers this recording and stops its tracks', async () => {
  const stream = new FakeStream();
  const controller = controllerWith(async () => stream);
  const recorded = [];
  await controller.start(CONSTRAINTS, 'audio/webm', (blob, mimeType) => recorded.push({ blob, mimeType }));
  controller.stop();
  assert.equal(stream.stopped, true);
  assert.equal(recorded.length, 1);
  assert.equal(await recorded[0].blob.text(), 'chunk');
  assert.equal(recorded[0].mimeType, 'audio/webm');
  assert.equal(controller.state, 'idle');
});

test('each recording keeps its own chunks and stream', async () => {
  const streams = [new FakeStream(), new FakeStream()];
  const controller = controllerWith(async () => streams.shift());
  const recorded = [];
  const first = await controller.start(CONSTRAINTS, '', (blob) => recorded.push(blob));
  controller.stop();
  const second = await controller.start(CONSTRAINTS, '', (blob) => recorded.push(blob));
  controller.stop();
  assert.notEqual(first, second);
  assert.equal(first.stopped && second.stopped, true);
  assert.deepEqual(await Promise.all(recorded.map((blob) => blob.text())), ['chunk', 'chunk']);
});

test('dispose during a pending start stops the stream that arrives later', async () => {
  const pending = deferred();
  const controller = controllerWith(() => pending.promise);
  const started = controller.start(CONSTRAINTS, '', () => assert.fail('no recording expected'));
  controller.dispose();
  const stream = new FakeStream();
  pending.resolve(stream);
  assert.equal(await started, null);
  assert.equal(stream.stopped, true);
});

test('dispose while recording stops the tracks and drops the recording', async () => {
  const stream = new FakeStream();
  const controller = controllerWith(async () => stream);
  await controller.start(CONSTRAINTS, '', () => assert.fail('no recording expected'));
  controller.dispose();
  assert.equal(stream.stopped, true);
});

test('a recorder that cannot be created releases the stream and allows a retry', async () => {
  const stream = new FakeStream();
  const controller = controllerWith(async () => stream, () => { throw new Error('unsupported'); });
  await assert.rejects(controller.start(CONSTRAINTS, '', () => {}), /unsupported/);
  assert.equal(stream.stopped, true);
  assert.equal(controller.state, 'idle');
});

test('a denied permission returns to idle', async () => {
  const controller = controllerWith(async () => { throw new Error('denied'); });
  await assert.rejects(controller.start(CONSTRAINTS, '', () => {}), /denied/);
  assert.equal(controller.state, 'idle');
});
