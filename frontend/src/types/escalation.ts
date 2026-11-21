import type { TicketPriority, TicketStatus } from './ticket';
import type { User } from './user';

export type EscalationStatus = 'active' | 'resolved';

export interface Escalation {
  id: number;
  ticket_id: number;
  escalated_to: User;
  escalated_by: string;
  level: number;
  reason: string;
  status: EscalationStatus;
  source: 'manual' | 'auto';
  notification_sent: boolean;
  customer_notified: boolean;
  auto_assigned: boolean;
  resolution_note: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface EscalationWithTicket extends Escalation {
  ticket: {
    id: number;
    ticket_number: string;
    subject: string;
    status: TicketStatus;
    priority: TicketPriority;
    requester_email: string;
    requester_name: string | null;
  };
}

export interface EscalationCreateInput {
  /** Omit to auto-assign the best contact. */
  escalated_to_id?: number;
  reason: string;
  reassign: boolean;
  notify_customer: boolean;
}

export interface EmailPreview {
  to: string;
  subject: string;
  body: string;
}

export interface EscalationSuggestion {
  contact: User;
  level: number;
  team: string;
  reasons: string[];
  customer_email: EmailPreview;
}
