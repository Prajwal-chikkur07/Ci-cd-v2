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
  const { currentPipeline, stageStatuses, isExecuting } = usePipelineContext();

  // Determine agent status from stage statuses
  const agentStatus: Record<AgentType, { status: 'running' | 'idle' | 'done' | 'failed'; task?: string }> = {
    build: { status: 'idle' }, test: { status: 'idle' }, security: { status: 'idle' },
    deploy: { status: 'idle' }, verify: { status: 'idle' },
  };

  if (currentPipeline) {
    for (const stage of currentPipeline.stages) {
      const s = stageStatuses.get(stage.id) ?? 'pending';
      const agent = stage.agent;
      if (s === 'running') {
        agentStatus[agent] = { status: 'running', task: stage.id };
      } else if (s === 'failed' && agentStatus[agent].status !== 'running') {
        agentStatus[agent] = { status: 'failed', task: stage.id };
      } else if (s === 'success' && agentStatus[agent].status === 'idle') {
        agentStatus[agent] = { status: 'done', task: stage.id };
      }
    }
  }

  return (
    <div className="w-[220px] flex-shrink-0 flex flex-col gap-3">
      {/* Agent Activity */}
      <div className="bg-[#111827] rounded-xl border border-[#1f2937] overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1f2937]">
          <Bot className="w-4 h-4 text-[#4b5563]" />
          <h3 className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider">Agent Activity</h3>
        </div>
        <div className="p-2 space-y-1">
          {ALL_AGENTS.map((agent) => {
            const color = agentColors[agent];
            const info = agentStatus[agent];
            const isRunning = info.status === 'running';
            return (
              <div
                key={agent}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isRunning ? 'bg-accent/10 border border-accent/20' : 'hover:bg-[#1f2937]'
                }`}
              >
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${color.color}15`, color: color.color }}
                >
                  {agentIcons[agent]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white">{color.label}</div>
                  <div className="text-[10px] text-[#4b5563] truncate">
                    {isRunning ? (info.task ?? 'Running...') : info.status === 'done' ? 'Completed' : info.status === 'failed' ? 'Failed' : 'Waiting for tasks...'}
                  </div>
                </div>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                    isRunning
                      ? 'bg-accent/20 text-accent'
                      : info.status === 'done'
                        ? 'bg-accent/10 text-accent/60'
                        : info.status === 'failed'
                          ? 'bg-red-900/30 text-red-400'
                          : 'bg-[#1f2937] text-[#4b5563]'
                  }`}
                >
                  {isRunning ? 'Running' : info.status === 'done' ? 'Done' : info.status === 'failed' ? 'Failed' : 'Idle'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Deployment Status */}
      <div className="bg-[#111827] rounded-xl border border-[#1f2937] overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1f2937]">
          <Activity className="w-4 h-4 text-[#4b5563]" />
          <h3 className="text-xs font-semibold text-[#9ca3af] uppercase tracking-wider">Deployment Status</h3>
        </div>
        <div className="p-4">
          {!currentPipeline ? (
            <p className="text-xs text-[#374151] text-center py-2">No active pipeline</p>
          ) : (
            <div className="space-y-2">
              {currentPipeline.stages.map((stage) => {
                const s = stageStatuses.get(stage.id) ?? 'pending';
                const color = s === 'success' ? '#10a37f' : s === 'failed' ? '#ef4444' : s === 'running' ? '#10a37f' : s === 'skipped' ? '#f59e0b' : '#374151';
                return (
                  <div key={stage.id} className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-xs text-[#9ca3af] truncate flex-1 capitalize">{stage.id.replace(/_/g, ' ')}</span>
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
