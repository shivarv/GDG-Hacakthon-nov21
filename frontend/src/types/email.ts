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
