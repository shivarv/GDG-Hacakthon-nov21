import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, EmptyState, ErrorMessage, Pagination, Spinner } from '@/components/common';
import { PageHeader } from '@/components/layout';
import { TicketFilters, TicketTable } from '@/components/tickets';
import { useTickets } from '@/hooks/useTickets';
import type { TicketFilters as Filters } from '@/types/ticket';

export function TicketsPage() {
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: 20 });
  const { data, loading, error, reload } = useTickets(filters);
  const onFiltersChange = useCallback((f: Filters) => setFilters(f), []);

  return (
    <>
      <PageHeader
        title="Tickets"
        subtitle="All cases from web and email"
        actions={<Link to="/tickets/new"><Button>New ticket</Button></Link>}
      />
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <TicketFilters filters={filters} onChange={onFiltersChange} />
        {loading ? (
          <Spinner />
        ) : error ? (
          <div className="p-4"><ErrorMessage message={error} onRetry={reload} /></div>
        ) : data && data.items.length > 0 ? (
          <>
            <TicketTable tickets={data.items} />
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(page) => setFilters({ ...filters, page })} />
          </>
        ) : (
          <EmptyState title="No tickets found" description="Try changing the filters, or send an email to the support inbox." />
        )}
      </section>
    </>
  );
}
