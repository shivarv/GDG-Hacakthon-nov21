import type { Comment } from '@/types/ticket';
import { cn, formatDateTime } from '@/utils/format';

export function CommentList({ comments }: { comments: Comment[] }) {
  if (comments.length === 0) {
    return <p className="py-6 text-center text-sm text-slate-500">No replies yet.</p>;
  }
  return (
    <ol className="space-y-4">
      {comments.map((c) => (
        <li
          key={c.id}
          className={cn(
            'rounded-lg border p-4',
            c.is_internal ? 'border-amber-200 bg-amber-50' : c.source === 'email' ? 'border-violet-200 bg-violet-50/50' : 'border-slate-200 bg-white',
          )}
        >
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-semibold text-slate-800">{c.author}</span>
            {c.source === 'email' && <span>✉ via email</span>}
            {c.is_internal && <span className="font-medium text-amber-700">🔒 Internal note</span>}
            <span className="ml-auto">{formatDateTime(c.created_at)}</span>
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-700">{c.body}</p>
        </li>
      ))}
    </ol>
  );
}
