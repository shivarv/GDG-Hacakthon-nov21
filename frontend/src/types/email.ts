export type EmailProcessingStatus = 'created_ticket' | 'appended_comment' | 'failed';

export interface EmailMessage {
  id: number;
  message_id: string;
  in_reply_to: string | null;
  from_address: string;
  from_name: string | null;
  to_address: string | null;
  subject: string;
  body_text: string;
  processing_status: EmailProcessingStatus;
  error: string | null;
  ticket_id: number | null;
  received_at: string;
}

export interface InboundEmailInput {
  from_address: string;
  from_name?: string;
  subject: string;
  body_text: string;
}

export interface EmailIngestResult {
  email_id: number;
  ticket_id: number | null;
  ticket_number: string | null;
  action: EmailProcessingStatus;
}

export interface InboxInfo {
  enabled: boolean;
  address: string | null;
}

export type OutboundEmailStatus = 'sent' | 'failed' | 'skipped';
export type OutboundEmailKind = 'acknowledgement' | 'escalation_internal' | 'customer_handoff' | 'test';

export interface OutboundEmail {
  id: number;
  ticket_id: number | null;
  kind: OutboundEmailKind;
  to_address: string;
  from_address: string;
  reply_to: string | null;
  subject: string;
  body: string;
  status: OutboundEmailStatus;
  error: string | null;
  created_at: string;
}

export interface SmtpStatus {
  enabled: boolean;
  host: string | null;
  from_address: string;
  reply_to: string;
}
