import { Check } from 'lucide-react';
import { Avatar } from '@/components/common';
import { ROLE_LABELS, type User } from '@/types/user';
import { cn } from '@/utils/format';

interface Props {
  contacts: User[];
  value: number | null;
  onChange: (id: number) => void;
  excludeId?: number;
}

const LEVEL_LABEL: Record<number, string> = { 2: 'Level 2 · Team leads', 3: 'Level 3 · Management, on-call & security' };

/** Radio-style list of escalation contacts, grouped by escalation level. */
export function ContactPicker({ contacts, value, onChange, excludeId }: Props) {
  const levels = [...new Set(contacts.map((c) => c.escalation_level))].sort();

  return (
    <div className="space-y-4">
      {levels.map((level) => (
        // min-w-0 overrides the browser default (min-content) so long team names truncate.
        <fieldset key={level} className="min-w-0">
          <legend className="label">{LEVEL_LABEL[level] ?? `Level ${level}`}</legend>
          <div className="divide-y divide-slate-100 overflow-hidden rounded-md border border-slate-200">
            {contacts
              .filter((c) => c.escalation_level === level)
              .map((c) => {
                const selected = value === c.id;
                const disabled = c.id === excludeId;
                return (
                  <button
                    type="button"
                    key={c.id}
                    disabled={disabled}
                    onClick={() => onChange(c.id)}
                    className={cn(
                      'flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors',
                      selected ? 'bg-brand-50' : 'hover:bg-slate-50',
                      disabled && 'cursor-not-allowed opacity-40',
                    )}
                  >
                    <Avatar name={c.name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">
                        {c.name} {disabled && <span className="text-xs font-normal text-slate-500">(current)</span>}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {ROLE_LABELS[c.role]} · {c.team}
                      </p>
                    </div>
                    <span className={cn('flex h-5 w-5 shrink-0 items-center justify-center rounded-full border', selected ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300')}>
                      {selected && <Check className="h-3 w-3" />}
                    </span>
                  </button>
                );
              })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
