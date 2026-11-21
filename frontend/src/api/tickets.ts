import { http } from './client';
import type { Page } from '@/types/common';
import type {
  Comment,
  CommentCreateInput,
  Ticket,
  TicketCreateInput,
  TicketDetail,
  TicketFilters,
  TicketStats,
  TicketUpdateInput,
} from '@/types/ticket';
import type { EmailMessage } from '@/types/email';
import type { Escalation, EscalationCreateInput, EscalationSuggestion } from '@/types/escalation';

export const ticketsApi = {
  list: (filters: TicketFilters) => http.get<Page<Ticket>>('/api/tickets', { ...filters }),
  get: (id: number) => http.get<TicketDetail>(`/api/tickets/${id}`),
  create: (data: TicketCreateInput) => http.post<Ticket>('/api/tickets', data),
  update: (id: number, data: TicketUpdateInput) => http.patch<Ticket>(`/api/tickets/${id}`, data),
  remove: (id: number) => http.delete<void>(`/api/tickets/${id}`),
  stats: () => http.get<TicketStats>('/api/tickets/stats'),
  addComment: (id: number, data: CommentCreateInput) =>
    http.post<Comment>(`/api/tickets/${id}/comments`, data),
  escalate: (id: number, data: EscalationCreateInput) => http.post<Escalation>(`/api/tickets/${id}/escalate`, data),
  escalationSuggestion: (id: number, contactId?: number) =>
    http.get<EscalationSuggestion>(`/api/tickets/${id}/escalation-suggestion`, { contact_id: contactId }),
  deEscalate: (id: number, note?: string) => http.post<Escalation>(`/api/tickets/${id}/de-escalate`, { note }),
  emails: (id: number) => http.get<EmailMessage[]>(`/api/tickets/${id}/emails`),
};
