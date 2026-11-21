import { http } from './client';
import type { Page } from '@/types/common';
import type { EmailIngestResult, EmailMessage, InboundEmailInput, InboxInfo, OutboundEmail, SmtpStatus } from '@/types/email';

export const emailsApi = {
  list: (page = 1, page_size = 20) => http.get<Page<EmailMessage>>('/api/emails', { page, page_size }),
  outbound: (page = 1, page_size = 20) => http.get<Page<OutboundEmail>>('/api/emails/outbound', { page, page_size }),
  smtpStatus: () => http.get<SmtpStatus>('/api/emails/smtp-status'),
  sendTest: (to: string) => http.post<OutboundEmail>('/api/emails/test', { to }),
  inbox: () => http.get<InboxInfo>('/api/emails/inbox'),
  sendInbound: (data: InboundEmailInput) => http.post<EmailIngestResult>('/api/emails/inbound', data),
};
