import { cn } from '@/utils/format';

interface Props {
  label: string;
  value: number;
  accent?: string;
  hint?: string;
}

export function StatCard({ label, value, accent = 'bg-brand-500', hint }: Props) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <span className={cn('absolute inset-y-0 left-0 w-1', accent)} />
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}
