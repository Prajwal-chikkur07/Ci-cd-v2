import { Hammer, FlaskConical, Shield, Rocket, Activity, Bot } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { agentColors } from '../utils/statusColors';
import type { AgentType } from '../types/pipeline';

const agentIcons: Record<AgentType, React.ReactNode> = {
  build:    <Hammer className="w-4 h-4" />,
  test:     <FlaskConical className="w-4 h-4" />,
  security: <Shield className="w-4 h-4" />,
  deploy:   <Rocket className="w-4 h-4" />,
  verify:   <Activity className="w-4 h-4" />,
};

const ALL_AGENTS: AgentType[] = ['build', 'test', 'security', 'deploy', 'verify'];

export default function AgentActivity() {
  const { currentPipeline, stageStatuses } = usePipelineContext();

  const agentStatus: Record<AgentType, { status: 'running' | 'idle' | 'done' | 'failed'; task?: string }> = {
    build: { status: 'idle' }, test: { status: 'idle' }, security: { status: 'idle' },
    deploy: { status: 'idle' }, verify: { status: 'idle' },
  };

  if (currentPipeline) {
    for (const stage of currentPipeline.stages) {
      const s = stageStatuses.get(stage.id) ?? 'pending';
      const agent = stage.agent;
      if (s === 'running') agentStatus[agent] = { status: 'running', task: stage.id };
      else if (s === 'failed' && agentStatus[agent].status !== 'running') agentStatus[agent] = { status: 'failed', task: stage.id };
      else if (s === 'success' && agentStatus[agent].status === 'idle') agentStatus[agent] = { status: 'done', task: stage.id };
    }
  }

  return (
    <div className="w-[200px] flex-shrink-0 flex flex-col gap-3">
      {/* Agent Activity */}
      <div className="bg-white rounded-xl border border-[#e5e7eb] shadow-card overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#f3f4f6]">
          <Bot className="w-4 h-4 text-[#6b7280]" />
          <h3 className="text-xs font-semibold text-[#374151] uppercase tracking-wider">Agents</h3>
        </div>
        <div className="divide-y divide-[#f3f4f6]">
          {ALL_AGENTS.map(agent => {
            const color = agentColors[agent];
            const info = agentStatus[agent];
            const isRunning = info.status === 'running';
            return (
              <div key={agent} className={`flex items-center gap-2.5 px-3 py-2.5 transition-colors ${isRunning ? 'bg-[#f9fafb]' : ''}`}>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#f3f4f6]" style={{ color: color.color }}>
                  {agentIcons[agent]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-[#111827]">{color.label.replace(' Agent', '')}</div>
                  <div className="text-[10px] text-[#9ca3af] truncate">
                    {isRunning ? (info.task ?? 'Running...') : info.status === 'done' ? 'Done' : info.status === 'failed' ? 'Failed' : 'Idle'}
                  </div>
                </div>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border flex-shrink-0 ${
                  isRunning ? 'bg-[#f0fdf4] text-[#16a34a] border-[#bbf7d0]'
                  : info.status === 'done' ? 'bg-[#f0fdf4] text-[#16a34a] border-[#bbf7d0]'
                  : info.status === 'failed' ? 'bg-[#fef2f2] text-[#dc2626] border-[#fecaca]'
                  : 'bg-[#f9fafb] text-[#9ca3af] border-[#e5e7eb]'
                }`}>
                  {isRunning ? '●' : info.status === 'done' ? '✓' : info.status === 'failed' ? '✗' : '○'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Deployment Status */}
      <div className="bg-white rounded-xl border border-[#e5e7eb] shadow-card overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#f3f4f6]">
          <Activity className="w-4 h-4 text-[#6b7280]" />
          <h3 className="text-xs font-semibold text-[#374151] uppercase tracking-wider">Stages</h3>
        </div>
        <div className="p-3">
          {!currentPipeline ? (
            <p className="text-xs text-[#9ca3af] text-center py-2">No active pipeline</p>
          ) : (
            <div className="space-y-1.5">
              {currentPipeline.stages.map(stage => {
                const s = stageStatuses.get(stage.id) ?? 'pending';
                const color = s === 'success' ? '#22c55e' : s === 'failed' ? '#ef4444' : s === 'running' ? '#111827' : s === 'skipped' ? '#f59e0b' : '#e5e7eb';
                return (
                  <div key={stage.id} className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-xs text-[#374151] truncate flex-1 capitalize">{stage.id.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] capitalize" style={{ color }}>{s}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
