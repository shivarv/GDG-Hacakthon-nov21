import { http } from './client';
import type { Page } from '@/types/common';
import type { EmailIngestResult, EmailMessage, InboundEmailInput, InboxInfo } from '@/types/email';

export const emailsApi = {
  list: (page = 1, page_size = 20) => http.get<Page<EmailMessage>>('/api/emails', { page, page_size }),
  inbox: () => http.get<InboxInfo>('/api/emails/inbox'),
  sendInbound: (data: InboundEmailInput) => http.post<EmailIngestResult>('/api/emails/inbound', data),
};
