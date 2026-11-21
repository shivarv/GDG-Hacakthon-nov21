import { Siren } from 'lucide-react';

export function EscalationBadge({ level }: { level?: number }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-md bg-red-50 px-1.5 py-0.5 text-[11px] font-semibold text-red-700 ring-1 ring-inset ring-red-200">
      <Siren className="h-3 w-3" />
      Escalated{level ? ` · L${level}` : ''}
    </span>
  );
}
