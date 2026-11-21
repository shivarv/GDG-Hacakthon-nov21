import { Link, useNavigate } from 'react-router-dom';
import { ticketsApi } from '@/api/tickets';
import { PageHeader } from '@/components/layout';
import { TicketForm } from '@/components/tickets';
import type { TicketCreateInput } from '@/types/ticket';
import { Breadcrumbs } from './Breadcrumbs';

export function NewTicketPage() {
  const navigate = useNavigate();

  const handleSubmit = async (data: TicketCreateInput) => {
    const ticket = await ticketsApi.create(data);
    navigate(`/tickets/${ticket.id}`);
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow={<Breadcrumbs items={[{ label: 'Tickets', to: '/tickets' }, { label: 'New' }]} />}
        title="Create ticket"
        description={<>Log a case on behalf of a customer. Cases from email are created automatically on the <Link to="/emails" className="text-brand-600 hover:underline">email channel</Link>.</>}
      />
      <TicketForm onSubmit={handleSubmit} onCancel={() => navigate(-1)} />
    </div>
  );
}
