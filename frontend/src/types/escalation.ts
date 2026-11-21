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
  first_response_due_at: string | null;
  resolution_due_at: string | null;
  eta_model: string | null;
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

export interface Eta {
  first_response_due_at: string;
  resolution_due_at: string;
  model: string;
  confidence: number;
  factors: string[];
}

export interface EscalationSuggestion {
  contact: User;
  level: number;
  team: string;
  reasons: string[];
  eta: Eta;
  customer_email: EmailPreview;
}
