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
    <div className="group rounded-xl border border-slate-200/80 bg-white p-4 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover sm:p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <span className={cn('flex h-10 w-10 items-center justify-center rounded-xl ring-1 ring-inset ring-black/5', iconClassName)}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight text-slate-900 sm:text-[2.125rem]">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
