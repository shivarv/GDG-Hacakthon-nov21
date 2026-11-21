import { Clock, Mail, Phone, Sparkles } from 'lucide-react';
import { Avatar } from '@/components/common';
import type { EscalationSuggestion } from '@/types/escalation';
import { ROLE_LABELS } from '@/types/user';
import { formatDateTime } from '@/utils/format';

/** The auto-assignment pick, with the reasons it was chosen. */
export function SuggestedContact({ suggestion: s }: { suggestion: EscalationSuggestion }) {
  return (
    <div className="rounded-md border border-brand-200 bg-brand-50/50 p-4">
      <div className="flex items-start gap-3">
        <Avatar name={s.contact.name} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">{s.contact.name}</p>
            <span className="rounded bg-white px-1.5 py-0.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">L{s.level}</span>
          </div>
          <p className="text-xs text-slate-500">{ROLE_LABELS[s.contact.role]} · {s.contact.team}</p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5 text-slate-400" />{s.contact.email}</span>
            {s.contact.phone && <span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5 text-slate-400" />{s.contact.phone}</span>}
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-brand-100 pt-3 text-xs">
        <div className="rounded bg-white px-2.5 py-1.5 ring-1 ring-inset ring-brand-100">
          <p className="text-slate-500">First response by</p>
          <p className="font-medium text-slate-900">{formatDateTime(s.eta.first_response_due_at)}</p>
        </div>
        <div className="rounded bg-white px-2.5 py-1.5 ring-1 ring-inset ring-brand-100">
          <p className="text-slate-500">Target resolution</p>
          <p className="font-medium text-slate-900">{formatDateTime(s.eta.resolution_due_at)}</p>
        </div>
        <p className="col-span-2 flex items-center gap-1 text-xs text-slate-500">
          <Clock className="h-3 w-3" /> Estimated by <code>{s.eta.model}</code> · {s.eta.factors.join(' · ')}
        </p>
      </div>
      <div className="mt-3 border-t border-brand-100 pt-3">
        <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-brand-700"><Sparkles className="h-3.5 w-3.5" /> Why this contact</p>
        <ul className="space-y-1">
          {s.reasons.map((r) => (
            <li key={r} className="flex gap-2 text-xs text-slate-600"><span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400" />{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
