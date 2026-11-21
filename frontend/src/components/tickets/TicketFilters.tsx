import { useEffect, useState } from 'react';
import { Select } from '@/components/common';
import {
  TICKET_PRIORITIES,
  TICKET_SOURCES,
  TICKET_STATUSES,
  type TicketFilters as Filters,
} from '@/types/ticket';

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function TicketFilters({ filters, onChange }: Props) {
  const [search, setSearch] = useState(filters.q ?? '');

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      if (search !== (filters.q ?? '')) onChange({ ...filters, q: search, page: 1 });
    }, 300);
    return () => clearTimeout(t);
  }, [search, filters, onChange]);

  return (
    <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
      <input
        className="input"
        placeholder="Search subject, description, email…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <Select
        options={TICKET_STATUSES}
        placeholder="All statuses"
        value={filters.status ?? ''}
        onValueChange={(status) => onChange({ ...filters, status, page: 1 })}
      />
      <Select
        options={TICKET_PRIORITIES}
        placeholder="All priorities"
        value={filters.priority ?? ''}
        onValueChange={(priority) => onChange({ ...filters, priority, page: 1 })}
      />
      <Select
        options={TICKET_SOURCES}
        placeholder="All sources"
        value={filters.source ?? ''}
        onValueChange={(source) => onChange({ ...filters, source, page: 1 })}
      />
    </div>
  );
}
