import { emailsApi } from '@/api/emails';
import { useAsync } from './useAsync';

export function useEmails(page: number) {
  return useAsync(() => emailsApi.list(page), [page]);
}
