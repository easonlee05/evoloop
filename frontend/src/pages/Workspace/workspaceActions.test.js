import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldShowRunPrompt, getDocumentActionLabel } from './workspaceActions.js';

test('shouldShowRunPrompt is true for resumable unfinished tasks', () => {
  assert.equal(shouldShowRunPrompt('created'), true);
  assert.equal(shouldShowRunPrompt('cancelled'), true);
  assert.equal(shouldShowRunPrompt('waiting_for_user'), true);
  assert.equal(shouldShowRunPrompt('completed'), false);
  assert.equal(shouldShowRunPrompt('failed'), false);
});

test('getDocumentActionLabel matches document availability', () => {
  assert.equal(getDocumentActionLabel({ done: true }), '查看文档');
  assert.equal(getDocumentActionLabel({ done: false }), '打开文档');
});
