import { cn } from '@/utils/format';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** Underline tabs that scroll horizontally on narrow screens. */
export function Tabs<T extends string>({ items, value, onChange }: TabsProps<T>) {
  return (
    <div className="-mb-px flex gap-6 overflow-x-auto px-4 sm:px-6" role="tablist">
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              'flex shrink-0 items-center gap-2 border-b-2 py-3.5 text-sm font-semibold transition-colors',
              active ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span className={cn('rounded-full px-2 py-0.5 text-xs tabular-nums', active ? 'bg-brand-50 text-brand-700' : 'bg-slate-100 text-slate-600')}>
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
