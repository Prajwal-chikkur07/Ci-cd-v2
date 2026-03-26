import type { AgentType, StageStatus } from '../types/pipeline';

export const statusConfig: Record<StageStatus, {
  border: string; bg: string; text: string; label: string;
}> = {
  pending:  { border: '#e5e7eb', bg: '#f9fafb', text: '#9ca3af', label: 'Pending' },
  running:  { border: '#111827', bg: '#f9fafb', text: '#111827', label: 'Running' },
  success:  { border: '#22c55e', bg: '#f0fdf4', text: '#16a34a', label: 'Success' },
  failed:   { border: '#ef4444', bg: '#fef2f2', text: '#dc2626', label: 'Failed'  },
  skipped:  { border: '#f59e0b', bg: '#fffbeb', text: '#d97706', label: 'Skipped' },
};

export const agentColors: Record<AgentType, { color: string; label: string }> = {
  build:    { color: '#111827', label: 'Build Agent'        },
  test:     { color: '#3b82f6', label: 'Test Agent'         },
  security: { color: '#ef4444', label: 'Security Agent'     },
  deploy:   { color: '#f59e0b', label: 'Deploy Agent'       },
  verify:   { color: '#8b5cf6', label: 'Verification Agent' },
};
