// Brings the current-run panel in line with stored results, for WebSocket events that were
// missed while the socket was disconnected.

const FINISHED = new Set(['completed', 'failed']);

export function hasProcessing(results) {
  return results.some((result) => result.status === 'processing');
}

export function reconcileCurrent(current, results) {
  if (!current || FINISHED.has(current.status)) return current;
  const stored = results.find((result) => result.id === current.analysis_id);
  if (!stored || !FINISHED.has(stored.status)) return current;
  const failed = stored.status === 'failed';
  return {
    type: failed ? 'analysis_error' : 'analysis_complete',
    analysis_id: stored.id,
    status: stored.status,
    message: failed ? stored.error_message || 'Analysis failed' : 'Analysis completed',
  };
}
