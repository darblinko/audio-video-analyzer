// Run with: npm test (node --test).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hasProcessing, reconcileCurrent } from './reconcile.js';

const processing = { analysis_id: 'a1', status: 'processing', message: 'Queued' };

test('a run that finished while disconnected is shown as completed', () => {
  const results = [{ id: 'a1', status: 'completed' }];
  assert.deepEqual(reconcileCurrent(processing, results), {
    type: 'analysis_complete',
    analysis_id: 'a1',
    status: 'completed',
    message: 'Analysis completed',
  });
});

test('a progress message without a status is reconciled as well', () => {
  const progress = { type: 'progress', analysis_id: 'a1', step: 'gemini', message: 'Describing' };
  const results = [{ id: 'a1', status: 'failed', error_message: 'Audio analysis failed' }];
  assert.deepEqual(reconcileCurrent(progress, results), {
    type: 'analysis_error',
    analysis_id: 'a1',
    status: 'failed',
    message: 'Audio analysis failed',
  });
});

test('a run still processing, or not in the results, is left unchanged', () => {
  assert.equal(reconcileCurrent(processing, [{ id: 'a1', status: 'processing' }]), processing);
  assert.equal(reconcileCurrent(processing, []), processing);
  assert.equal(reconcileCurrent(null, [{ id: 'a1', status: 'completed' }]), null);
});

test('hasProcessing reports whether any stored run is outstanding', () => {
  assert.equal(hasProcessing([{ status: 'completed' }, { status: 'processing' }]), true);
  assert.equal(hasProcessing([{ status: 'failed' }]), false);
});
