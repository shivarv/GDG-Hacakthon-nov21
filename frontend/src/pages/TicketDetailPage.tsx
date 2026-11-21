import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, Trash2 } from 'lucide-react';
import { ticketsApi } from '@/api/tickets';
import { Button, Card, ErrorMessage, Spinner } from '@/components/common';
import { PageHeader } from '@/components/layout';
import { CommentForm, CommentList, PriorityBadge, SourceBadge, StatusBadge, TicketPropertiesPanel } from '@/components/tickets';
import { useTicket } from '@/hooks/useTickets';
import type { CommentCreateInput, TicketUpdateInput } from '@/types/ticket';
import { timeAgo } from '@/utils/format';
import { Breadcrumbs } from './Breadcrumbs';

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

  const isDone = ticket.status === 'resolved' || ticket.status === 'closed';

  return (
    <>
      <PageHeader
        eyebrow={<Breadcrumbs items={[{ label: 'Tickets', to: '/tickets' }, { label: ticket.ticket_number }]} />}
        title={ticket.subject}
        description={
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <SourceBadge source={ticket.source} />
            <span className="text-xs text-slate-500">Opened {timeAgo(ticket.created_at)}</span>
          </div>
        }
        actions={
          <>
            <Button variant="danger" onClick={handleDelete} icon={<Trash2 className="h-4 w-4" />}>
              <span className="hidden sm:inline">Delete</span>
            </Button>
            {!isDone && (
              <Button onClick={() => handleUpdate({ status: 'resolved' })} icon={<CheckCircle2 className="h-4 w-4" />}>
                Mark resolved
              </Button>
            )}
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Conversation" description={`${ticket.comments.length + 1} messages`}>
          <CommentList ticket={ticket} comments={ticket.comments} />
          <div className="mt-6 sm:pl-12">
            <CommentForm onSubmit={handleComment} />
          </div>
        </Card>
        <TicketPropertiesPanel key={ticket.updated_at} ticket={ticket} onUpdate={handleUpdate} />
      </div>
    </>
  );
}
