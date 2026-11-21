import { useNavigate } from 'react-router-dom';
import { ticketsApi } from '@/api/tickets';
import { Card } from '@/components/common';
import { PageHeader } from '@/components/layout';
import { TicketForm } from '@/components/tickets';
import type { TicketCreateInput } from '@/types/ticket';

export function NewTicketPage() {
  const navigate = useNavigate();

  const handleSubmit = async (data: TicketCreateInput) => {
    const ticket = await ticketsApi.create(data);
    navigate(`/tickets/${ticket.id}`);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="New ticket" subtitle="Log a case on behalf of a customer" />
      <Card>
        <TicketForm onSubmit={handleSubmit} onCancel={() => navigate(-1)} />
      </Card>
    </div>
  );
}
