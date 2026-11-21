import type { ReactNode } from 'react';
import { cn } from '@/utils/format';

interface CardProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function Card({ title, description, actions, className, bodyClassName, children }: CardProps) {
  return (
    <section className={cn('rounded-xl border border-slate-200/80 bg-white shadow-card', className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {/* bodyClassName replaces the default padding rather than competing with it. */}
      <div className={bodyClassName ?? 'p-4 sm:p-6'}>{children}</div>
    </section>
  );
}
