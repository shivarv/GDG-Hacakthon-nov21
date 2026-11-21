import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CheckCircle2, Siren, Trash2 } from 'lucide-react';
import { ticketsApi } from '@/api/tickets';
import { Button, Card, ErrorMessage, Spinner } from '@/components/common';
import { EscalateDialog, EscalationBanner, EscalationHistory } from '@/components/escalations';
import { PageHeader } from '@/components/layout';
import { CommentForm, CommentList, PriorityBadge, SourceBadge, StatusBadge, TicketPropertiesPanel } from '@/components/tickets';
import { useTicket } from '@/hooks/useTickets';
import { ESCALATABLE_STATUSES, type CommentCreateInput, type TicketUpdateInput } from '@/types/ticket';
import { notifyEscalationsChanged } from '@/utils/events';
import { timeAgo } from '@/utils/format';
import { Breadcrumbs } from './Breadcrumbs';

export function TicketDetailPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { data: ticket, loading, error, reload, setData } = useTicket(id);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deEscalating, setDeEscalating] = useState(false);

  if (loading) return <Spinner />;
  if (error || !ticket) return <ErrorMessage message={error ?? 'Ticket not found'} onRetry={reload} />;

  // Re-fetch without the full-page spinner (status changes can also close escalations server-side).
  const refresh = async () => setData(await ticketsApi.get(id));

  const handleUpdate = async (data: TicketUpdateInput) => {
    await ticketsApi.update(id, data);
    await refresh();
    notifyEscalationsChanged(); // resolving/closing also closes any escalation
  };

  const handleComment = async (data: CommentCreateInput) => {
    const comment = await ticketsApi.addComment(id, data);
    setData({ ...ticket, comments: [...ticket.comments, comment] });
    return comment;
  };

  const handleDelete = async () => {
    if (!confirm(`Delete ${ticket.ticket_number}? This cannot be undone.`)) return;
    await ticketsApi.remove(id);
    navigate('/tickets');
  };

  const handleDeEscalate = async () => {
    const note = prompt('Optional note for de-escalating:') ?? undefined;
    setDeEscalating(true);
    try {
      await ticketsApi.deEscalate(id, note || undefined);
      await refresh();
      notifyEscalationsChanged();
    } finally {
      setDeEscalating(false);
    }
  };

  const isDone = ticket.status === 'resolved' || ticket.status === 'closed';
  const activeEscalation = ticket.escalations.find((e) => e.status === 'active');
  const canEscalate = ESCALATABLE_STATUSES.includes(ticket.status) && !activeEscalation;

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
            {canEscalate && (
              <Button variant="danger" onClick={() => setDialogOpen(true)} icon={<Siren className="h-4 w-4" />}>
                Escalate
              </Button>
            )}
            {!isDone && (
              <Button onClick={() => handleUpdate({ status: 'resolved' })} icon={<CheckCircle2 className="h-4 w-4" />}>
                Mark resolved
              </Button>
            )}
          </>
        }
      />
      {activeEscalation && (
        <EscalationBanner
          escalation={activeEscalation}
          busy={deEscalating}
          onDeEscalate={handleDeEscalate}
          onReEscalate={() => setDialogOpen(true)}
        />
      )}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Conversation" description={`${ticket.comments.length + 1} messages`}>
          <CommentList ticket={ticket} comments={ticket.comments} />
          <div className="mt-6 sm:pl-12">
            <CommentForm onSubmit={handleComment} requesterEmail={ticket.requester_email} />
          </div>
        </Card>
        <div className="space-y-6">
          <TicketPropertiesPanel key={ticket.updated_at} ticket={ticket} onUpdate={handleUpdate} />
          <EscalationHistory escalations={ticket.escalations} />
        </div>
      </div>
      <EscalateDialog
        ticket={dialogOpen ? ticket : null}
        currentContactId={activeEscalation?.escalated_to.id}
        onClose={() => setDialogOpen(false)}
        onEscalated={() => {
          setDialogOpen(false);
          void refresh();
        }}
      />
    </>
  );
}
