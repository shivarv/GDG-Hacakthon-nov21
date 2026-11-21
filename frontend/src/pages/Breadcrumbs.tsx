import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-slate-500" aria-label="Breadcrumb">
      {items.map((item, i) => (
        <span key={item.label} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-400" />}
          {item.to ? <Link to={item.to} className="hover:text-slate-700">{item.label}</Link> : <span className="text-slate-700">{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}
