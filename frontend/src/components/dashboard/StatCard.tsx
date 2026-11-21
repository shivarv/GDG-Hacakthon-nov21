import type { LucideIcon } from 'lucide-react';
import { cn } from '@/utils/format';

interface Props {
  label: string;
  value: number;
  icon: LucideIcon;
  iconClassName?: string;
  hint?: string;
}

export function StatCard({ label, value, icon: Icon, iconClassName = 'bg-brand-50 text-brand-600', hint }: Props) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-card sm:p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className={cn('flex h-8 w-8 items-center justify-center rounded-md', iconClassName)}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums tracking-tight text-slate-900 sm:text-3xl">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
