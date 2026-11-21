import { http } from './client';
import type { EscalationStatus, EscalationWithTicket } from '@/types/escalation';
import type { User } from '@/types/user';

export const escalationsApi = {
  list: (status: EscalationStatus = 'active') => http.get<EscalationWithTicket[]>('/api/escalations', { status }),
  contacts: () => http.get<User[]>('/api/users', { escalation_contacts: true }),
};
