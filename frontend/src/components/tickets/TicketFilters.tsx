import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { Select } from '@/components/common';
import { TICKET_PRIORITIES, TICKET_SOURCES, type TicketFilters as Filters } from '@/types/ticket';

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

/** Search + priority/source filters. Status is handled by tabs on the page. */
export function TicketFilters({ filters, onChange }: Props) {
  const [search, setSearch] = useState(filters.q ?? '');

  useEffect(() => setSearch(filters.q ?? ''), [filters.q]);

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      if (search !== (filters.q ?? '')) onChange({ ...filters, q: search, page: 1 });
    }, 300);
    return () => clearTimeout(t);
  }, [search, filters, onChange]);

  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 bg-slate-50/60 px-4 py-3 sm:flex-row sm:items-center sm:px-6">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          className="input pl-9"
          placeholder="Search by subject, description or requester…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:flex sm:w-auto">
        <Select
          className="sm:w-40"
          options={TICKET_PRIORITIES}
          placeholder="Any priority"
          value={filters.priority ?? ''}
          onValueChange={(priority) => onChange({ ...filters, priority, page: 1 })}
        />
        <Select
          className="sm:w-36"
          options={TICKET_SOURCES}
          placeholder="Any channel"
          value={filters.source ?? ''}
          onValueChange={(source) => onChange({ ...filters, source, page: 1 })}
        />
      </div>
    </div>
  );
}
