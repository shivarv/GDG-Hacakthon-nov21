import type { ReactNode } from 'react';
import { cn } from '@/utils/format';

export type BadgeTone = 'gray' | 'blue' | 'amber' | 'green' | 'red' | 'purple' | 'orange';

const tones: Record<BadgeTone, { pill: string; dot: string }> = {
  gray: { pill: 'bg-slate-100 text-slate-700', dot: 'bg-slate-400' },
  blue: { pill: 'bg-blue-50 text-blue-700', dot: 'bg-blue-500' },
  amber: { pill: 'bg-amber-50 text-amber-800', dot: 'bg-amber-500' },
  green: { pill: 'bg-emerald-50 text-emerald-700', dot: 'bg-emerald-500' },
  red: { pill: 'bg-red-50 text-red-700', dot: 'bg-red-500' },
  purple: { pill: 'bg-violet-50 text-violet-700', dot: 'bg-violet-500' },
  orange: { pill: 'bg-orange-50 text-orange-700', dot: 'bg-orange-500' },
};

interface BadgeProps {
  tone?: BadgeTone;
  dot?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

export function Badge({ tone = 'gray', dot, icon, children }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium', tones[tone].pill)}>
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', tones[tone].dot)} />}
      {icon}
      {children}
    </span>
  );
}
