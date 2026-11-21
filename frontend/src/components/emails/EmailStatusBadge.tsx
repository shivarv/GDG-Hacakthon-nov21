import { Badge, type BadgeTone } from '@/components/common';
import type { EmailProcessingStatus } from '@/types/email';

const config: Record<EmailProcessingStatus, { tone: BadgeTone; label: string }> = {
  created_ticket: { tone: 'green', label: 'New case' },
  appended_comment: { tone: 'blue', label: 'Reply threaded' },
  failed: { tone: 'red', label: 'Failed' },
};

export function EmailStatusBadge({ status }: { status: EmailProcessingStatus }) {
  const { tone, label } = config[status];
  return <Badge tone={tone}>{label}</Badge>;
}
