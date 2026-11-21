export type UserRole = 'agent' | 'team_lead' | 'manager' | 'on_call' | 'security';

export const ROLE_LABELS: Record<UserRole, string> = {
  agent: 'Agent',
  team_lead: 'Team Lead',
  manager: 'Manager',
  on_call: 'On-call Engineer',
  security: 'Security Officer',
};

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  team: string;
  escalation_level: number;
  is_escalation_contact: boolean;
}
