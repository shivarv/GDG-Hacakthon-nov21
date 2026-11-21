import { Link } from 'react-router-dom';
import { FileQuestion } from 'lucide-react';
import { Button, EmptyState } from '@/components/common';

export function NotFoundPage() {
  return (
    <EmptyState
      icon={FileQuestion}
      title="Page not found"
      description="The page you're looking for doesn't exist or has moved."
      action={<Link to="/"><Button>Back to overview</Button></Link>}
    />
  );
}
