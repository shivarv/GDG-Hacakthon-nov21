import { Globe, Mail } from 'lucide-react';
import type { TicketSource } from '@/types/ticket';

export function SourceBadge({ source }: { source: TicketSource }) {
  const Icon = source === 'email' ? Mail : Globe;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-slate-600">
      <Icon className="h-3.5 w-3.5 text-slate-400" />
      {source === 'email' ? 'Email' : 'Web'}
    </span>
  );
}
