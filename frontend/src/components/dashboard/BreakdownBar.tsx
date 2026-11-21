import { humanize } from '@/utils/format';

interface Props {
  data: Record<string, number | undefined>;
  order: readonly string[];
  colors: Record<string, string>;
}

/** A single stacked bar with a legend table underneath. */
export function BreakdownBar({ data, order, colors }: Props) {
  const total = order.reduce((sum, k) => sum + (data[k] ?? 0), 0);

  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        {order.map((key) => {
          const value = data[key] ?? 0;
          return value ? (
            <div key={key} className={colors[key]} style={{ width: `${(value / total) * 100}%` }} title={`${humanize(key)}: ${value}`} />
          ) : null;
        })}
      </div>
      <ul className="mt-4 divide-y divide-slate-100">
        {order.map((key) => {
          const value = data[key] ?? 0;
          const pct = total ? Math.round((value / total) * 100) : 0;
          return (
            <li key={key} className="flex items-center gap-3 py-2 text-sm">
              <span className={`h-2.5 w-2.5 rounded-sm ${colors[key]}`} />
              <span className="flex-1 text-slate-600">{humanize(key)}</span>
              <span className="w-10 text-right text-xs tabular-nums text-slate-400">{pct}%</span>
              <span className="w-8 text-right font-medium tabular-nums text-slate-900">{value}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
