import { humanize } from '@/utils/format';

interface Props {
  data: Record<string, number | undefined>;
  order: readonly string[];
  colors: Record<string, string>;
}

/** Horizontal list of labelled bars showing each bucket's share of the total. */
export function BreakdownBar({ data, order, colors }: Props) {
  const total = order.reduce((sum, k) => sum + (data[k] ?? 0), 0);
  return (
    <ul className="space-y-3">
      {order.map((key) => {
        const value = data[key] ?? 0;
        const pct = total ? Math.round((value / total) * 100) : 0;
        return (
          <li key={key}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-slate-600">{humanize(key)}</span>
              <span className="font-medium tabular-nums text-slate-900">{value}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div className={`h-2 rounded-full ${colors[key]}`} style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
