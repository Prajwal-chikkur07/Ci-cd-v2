import type { AgentType, StageStatus } from '../types/pipeline';

export const statusConfig: Record<StageStatus, {
  border: string;
  bg: string;
  text: string;
  label: string;
}> = {
  pending:  { border: '#374151', bg: '#1f2937',  text: '#94a3b8', label: 'Pending' },
  running:  { border: '#10a37f', bg: '#064e3b22', text: '#10a37f', label: 'Running' },
  success:  { border: '#10a37f', bg: '#064e3b33', text: '#10a37f', label: 'Success' },
  failed:   { border: '#ef4444', bg: '#7f1d1d22', text: '#ef4444', label: 'Failed' },
  skipped:  { border: '#f59e0b', bg: '#78350f22', text: '#f59e0b', label: 'Skipped' },
};

export const agentColors: Record<AgentType, { color: string; label: string }> = {
  build:    { color: '#10a37f', label: 'Build Agent' },
  test:     { color: '#60a5fa', label: 'Test Agent' },
  security: { color: '#f87171', label: 'Security Agent' },
  deploy:   { color: '#fb923c', label: 'Deploy Agent' },
  verify:   { color: '#a78bfa', label: 'Verification Agent' },
};
