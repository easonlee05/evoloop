export function shouldAutoOpenDocument({ reason, hasUserOpenedDoc }) {
  if (reason === 'writer-event') {
    return Boolean(hasUserOpenedDoc);
  }
  return false;
}

export function shouldAutoRunTaskOnOpen() {
  return false;
}
