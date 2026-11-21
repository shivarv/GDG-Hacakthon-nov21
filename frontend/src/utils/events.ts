/** Tiny app-wide signal so the sidebar badge refreshes after escalation changes. */
const EVENT = 'escalations:changed';

export const notifyEscalationsChanged = () => window.dispatchEvent(new Event(EVENT));

export function onEscalationsChanged(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
