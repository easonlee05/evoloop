import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldAutoOpenDocument, shouldAutoRunTaskOnOpen } from './workspaceSession.js';

test('shouldAutoOpenDocument stays closed for existing tasks on entry and writer updates', () => {
  assert.equal(shouldAutoOpenDocument({ reason: 'task-entry', hasUserOpenedDoc: false }), false);
  assert.equal(shouldAutoOpenDocument({ reason: 'writer-event', hasUserOpenedDoc: false }), false);
  assert.equal(shouldAutoOpenDocument({ reason: 'writer-event', hasUserOpenedDoc: true }), true);
});

test('shouldAutoRunTaskOnOpen never auto-runs created or unfinished tasks on open', () => {
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'created' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'running' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'waiting_for_user' }), false);
  assert.equal(shouldAutoRunTaskOnOpen({ rawStatus: 'cancelled' }), false);
});
