import { Link, useNavigate, useParams } from 'react-router-dom';
import { ticketsApi } from '@/api/tickets';
import { Button, Card, ErrorMessage, Spinner } from '@/components/common';
import { PageHeader } from '@/components/layout';
import {
  CommentForm,
  CommentList,
  PriorityBadge,
  StatusBadge,
  TicketPropertiesPanel,
} from '@/components/tickets';
import { useTicket } from '@/hooks/useTickets';
import type { CommentCreateInput, TicketUpdateInput } from '@/types/ticket';

export function TicketDetailPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { data: ticket, loading, error, reload, setData } = useTicket(id);

  if (loading) return <Spinner />;
  if (error || !ticket) return <ErrorMessage message={error ?? 'Ticket not found'} onRetry={reload} />;

  const handleUpdate = async (data: TicketUpdateInput) => {
    const updated = await ticketsApi.update(id, data);
    setData({ ...ticket, ...updated });
  };

  const handleComment = async (data: CommentCreateInput) => {
    const comment = await ticketsApi.addComment(id, data);
    setData({ ...ticket, comments: [...ticket.comments, comment] });
  };

  const handleDelete = async () => {
    if (!confirm(`Delete ${ticket.ticket_number}? This cannot be undone.`)) return;
    await ticketsApi.remove(id);
    navigate('/tickets');
  };

  return (
    <>
      <Link to="/tickets" className="mb-4 inline-block text-sm text-slate-500 hover:text-slate-700">← Back to tickets</Link>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-base text-slate-400">{ticket.ticket_number}</span>
            {ticket.subject}
          </span>
        }
        subtitle={
          <span className="flex gap-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
          </span>
        }
        actions={<Button variant="danger" onClick={handleDelete}>Delete</Button>}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Description">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{ticket.description || 'No description provided.'}</p>
          </Card>
          <Card title={`Conversation (${ticket.comments.length})`}>
            <CommentList comments={ticket.comments} />
            <div className="mt-6 border-t border-slate-100 pt-6">
              <CommentForm onSubmit={handleComment} />
            </div>
          </Card>
        </div>
        <TicketPropertiesPanel key={ticket.updated_at} ticket={ticket} onUpdate={handleUpdate} />
      </div>
    </>
  );
}
