import { Lock, Mail } from 'lucide-react';
import { Avatar } from '@/components/common';
import type { Comment, Ticket } from '@/types/ticket';
import { cn, formatDateTime } from '@/utils/format';

interface Props {
  ticket: Ticket;
  comments: Comment[];
}

/** Conversation timeline: the original request followed by every reply and note. */
export function CommentList({ ticket, comments }: Props) {
  const requester = ticket.requester_name ?? ticket.requester_email;

  return (
    <ol className="space-y-6">
      <Entry
        author={requester}
        meta={ticket.source === 'email' ? 'opened via email' : 'opened this case'}
        time={ticket.created_at}
        body={ticket.description || 'No description provided.'}
        viaEmail={ticket.source === 'email'}
        highlight
      />
      {comments.map((c) => (
        <Entry
          key={c.id}
          author={c.author}
          meta={c.is_internal ? 'added an internal note' : c.source === 'email' ? 'replied via email' : 'replied'}
          time={c.created_at}
          body={c.body}
          internal={c.is_internal}
          viaEmail={c.source === 'email'}
        />
      ))}
    </ol>
  );
}

interface EntryProps {
  author: string;
  meta: string;
  time: string;
  body: string;
  internal?: boolean;
  viaEmail?: boolean;
  highlight?: boolean;
}

function Entry({ author, meta, time, body, internal, viaEmail, highlight }: EntryProps) {
  return (
    <li className="flex gap-3 sm:gap-4">
      <Avatar name={author} className="mt-0.5 hidden sm:inline-flex" />
      <div
        className={cn(
          'min-w-0 flex-1 rounded-lg border',
          internal ? 'border-amber-200 bg-amber-50/70' : highlight ? 'border-slate-200 bg-slate-50' : 'border-slate-200 bg-white',
        )}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-inherit px-4 py-2.5 text-sm">
          <span className="font-medium text-slate-900">{author}</span>
          <span className="text-slate-500">{meta}</span>
          {viaEmail && <Mail className="h-3.5 w-3.5 text-slate-400" aria-label="via email" />}
          {internal && (
            <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
              <Lock className="h-3 w-3" /> Internal
            </span>
          )}
          <time className="ml-auto text-xs text-slate-400">{formatDateTime(time)}</time>
        </div>
        <p className="whitespace-pre-wrap break-words px-4 py-3 text-sm leading-relaxed text-slate-700">{body}</p>
      </div>
    </li>
  );
}
