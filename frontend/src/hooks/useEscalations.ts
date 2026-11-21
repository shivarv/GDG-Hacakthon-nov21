import { escalationsApi } from '@/api/escalations';
import type { EscalationStatus } from '@/types/escalation';
import { useAsync } from './useAsync';

export function useEscalations(status: EscalationStatus) {
  return useAsync(() => escalationsApi.list(status), [status]);
}

export function useEscalationContacts() {
  return useAsync(() => escalationsApi.contacts(), []);
}
