import { Badge } from '@/components/common';
import type { TicketSource } from '@/types/ticket';

export function SourceBadge({ source }: { source: TicketSource }) {
  return <Badge tone={source === 'email' ? 'purple' : 'gray'}>{source === 'email' ? '✉ Email' : '🌐 Web'}</Badge>;
}
