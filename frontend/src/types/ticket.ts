export type TicketStatus = 'open' | 'in_progress' | 'pending' | 'resolved' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TicketSource = 'web' | 'email';

export const TICKET_STATUSES: TicketStatus[] = ['open', 'in_progress', 'pending', 'resolved', 'closed'];
export const TICKET_PRIORITIES: TicketPriority[] = ['low', 'medium', 'high', 'urgent'];
export const TICKET_SOURCES: TicketSource[] = ['web', 'email'];

export interface Ticket {
  id: number;
  ticket_number: string;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  source: TicketSource;
  requester_email: string;
  requester_name: string | null;
  assignee: string | null;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: number;
  ticket_id: number;
  author: string;
  body: string;
  is_internal: boolean;
  source: TicketSource;
  created_at: string;
}

export interface TicketDetail extends Ticket {
  comments: Comment[];
}

export interface TicketCreateInput {
  subject: string;
  description: string;
  priority: TicketPriority;
  requester_email: string;
  requester_name?: string;
  assignee?: string;
}

export type TicketUpdateInput = Partial<
  Pick<Ticket, 'subject' | 'description' | 'status' | 'priority' | 'assignee'>
>;

export interface CommentCreateInput {
  author: string;
  body: string;
  is_internal: boolean;
}

export interface TicketFilters {
  status?: TicketStatus | '';
  priority?: TicketPriority | '';
  source?: TicketSource | '';
  q?: string;
  page: number;
  page_size: number;
}

export interface TicketStats {
  total: number;
  by_status: Partial<Record<TicketStatus, number>>;
  by_priority: Partial<Record<TicketPriority, number>>;
  by_source: Partial<Record<TicketSource, number>>;
}
