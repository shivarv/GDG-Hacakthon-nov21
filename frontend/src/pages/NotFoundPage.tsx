import { Link } from 'react-router-dom';
import { EmptyState, Button } from '@/components/common';

export function NotFoundPage() {
  return (
    <EmptyState title="Page not found" description="The page you're looking for doesn't exist." action={<Link to="/"><Button>Go home</Button></Link>} />
  );
}
