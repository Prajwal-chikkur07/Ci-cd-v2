import { useNavigate } from 'react-router-dom';
import {
  CheckCircle, XCircle, Loader2, Activity, GitMerge,
  Clock, TrendingUp, Plus, Hammer, FlaskConical,
  Shield, Rocket, AlertTriangle, ArrowRight,
} from 'lucide-react';
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

function StatCard({ label, value, color, icon, sub }: { label: string; value: string | number; color: string; icon: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-white border border-[#e5e7eb] rounded-xl p-5 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[#6b7280] uppercase tracking-wide">{label}</span>
        <span style={{ color }} className="opacity-70">{icon}</span>
      </div>
      <div className="text-2xl font-bold text-[#111827]">{value}</div>
      {sub && <div className="text-xs text-[#9ca3af] mt-1">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { executionHistory, activeExecutions, stageStatuses, currentPipeline } = usePipelineContext();

  const activeIds = new Set(activeExecutions.keys());
  const total   = executionHistory.length;
  const success = executionHistory.filter(e => e.overallStatus === 'success').length;
  const failed  = executionHistory.filter(e => e.overallStatus === 'failed').length;
  const running = activeIds.size;
  const successRate = total > 0 ? Math.round((success / total) * 100) : 0;
  const withDur = executionHistory.filter(e => e.duration_seconds);
  const avgDur = withDur.length > 0
    ? (withDur.reduce((s, e) => s + (e.duration_seconds ?? 0), 0) / withDur.length).toFixed(0)
    : null;

  const agentRunning: Record<AgentType, string | null> = { build: null, test: null, security: null, deploy: null, verify: null };
  if (currentPipeline) {
    for (const stage of currentPipeline.stages) {
      if (stageStatuses.get(stage.id) === 'running') agentRunning[stage.agent] = stage.id;
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-[#f9fafb]">
      {/* Header */}
      <div className="bg-white border-b border-[#e5e7eb] px-8 pt-7 pb-0">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Dashboard</h1>
            <p className="text-sm text-[#6b7280] mt-0.5">Overview of your CI/CD pipelines</p>
          </div>
          <button
            onClick={() => navigate('/pipelines')}
            className="flex items-center gap-2 px-4 py-2 bg-[#111827] hover:bg-[#1f2937] text-white text-sm font-medium rounded-lg transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            New Pipeline
          </button>
        </div>
      </div>

      <div className="px-8 py-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          <StatCard label="Total" value={total} color="#111827" icon={<GitMerge className="w-4 h-4" />} />
          <StatCard label="Successful" value={success} color="#22c55e" icon={<CheckCircle className="w-4 h-4" />} />
          <StatCard label="Failed" value={failed} color="#ef4444" icon={<XCircle className="w-4 h-4" />} />
          <StatCard label="Running" value={running} color="#3b82f6" icon={<Loader2 className="w-4 h-4" />} />
          <StatCard label="Success Rate" value={`${successRate}%`} color="#22c55e" icon={<TrendingUp className="w-4 h-4" />} />
          <StatCard label="Avg Duration" value={avgDur ? `${avgDur}s` : '—'} color="#8b5cf6" icon={<Clock className="w-4 h-4" />} />
        </div>

        {/* Two columns */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Recent pipelines */}
          <div className="bg-white border border-[#e5e7eb] rounded-xl shadow-card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#f3f4f6]">
              <h3 className="text-sm font-semibold text-[#111827]">Recent Pipelines</h3>
              <button onClick={() => navigate('/pipelines')} className="flex items-center gap-1 text-xs text-[#6b7280] hover:text-[#111827] transition-colors">
                View all <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {executionHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-[#9ca3af]">
                <Activity className="w-8 h-8 mb-3" />
                <p className="text-sm font-medium text-[#6b7280]">No pipelines yet</p>
                <p className="text-xs mt-1">Create your first pipeline to get started</p>
                <button onClick={() => navigate('/pipelines')}
                  className="mt-4 flex items-center gap-1.5 px-4 py-2 bg-[#111827] text-white text-xs font-medium rounded-lg hover:bg-[#1f2937] transition-colors">
                  <Plus className="w-3.5 h-3.5" /> Create Pipeline
                </button>
              </div>
            ) : (
              <div className="divide-y divide-[#f3f4f6]">
                {executionHistory.slice(0, 7).map((entry, i) => {
                  const isRunning = activeIds.has(entry.pipeline.pipeline_id);
                  const status = isRunning ? 'running' : entry.overallStatus;
                  const color = status === 'success' ? '#22c55e' : status === 'failed' ? '#ef4444' : '#3b82f6';
                  const icon = status === 'success'
                    ? <CheckCircle className="w-4 h-4" style={{ color }} />
                    : status === 'failed'
                      ? <XCircle className="w-4 h-4" style={{ color }} />
                      : <Loader2 className="w-4 h-4 animate-spin" style={{ color }} />;
                  return (
                    <button key={i} onClick={() => navigate(`/pipeline/${entry.pipeline.pipeline_id}`)}
                      className="w-full flex items-center gap-3 px-5 py-3 hover:bg-[#f9fafb] transition-colors text-left">
                      {icon}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-[#111827] truncate">
                          {entry.pipeline.name || entry.pipeline.repo_url.split('/').slice(-1)[0]}
                        </div>
                        <div className="text-xs text-[#9ca3af] truncate">{entry.pipeline.goal}</div>
                      </div>
                      <span className="text-xs text-[#9ca3af] flex-shrink-0">
                        {entry.duration_seconds ? `${entry.duration_seconds.toFixed(0)}s` : ''}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Agent status */}
          <div className="bg-white border border-[#e5e7eb] rounded-xl shadow-card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#f3f4f6]">
              <h3 className="text-sm font-semibold text-[#111827]">Agent Status</h3>
              <button onClick={() => navigate('/agents')} className="flex items-center gap-1 text-xs text-[#6b7280] hover:text-[#111827] transition-colors">
                View all <ArrowRight className="w-3 h-3" />
              </button>
            </div>
            <div className="divide-y divide-[#f3f4f6]">
              {ALL_AGENTS.map(agent => {
                const color = agentColors[agent];
                const task = agentRunning[agent];
                return (
                  <div key={agent} className="flex items-center gap-3 px-5 py-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-[#f3f4f6]" style={{ color: color.color }}>
                      {agentIcons[agent]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[#111827]">{color.label}</div>
                      <div className="text-xs text-[#9ca3af] truncate">{task ?? 'Waiting for tasks...'}</div>
                    </div>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                      task
                        ? 'bg-[#f0fdf4] text-[#16a34a] border-[#bbf7d0]'
                        : 'bg-[#f9fafb] text-[#9ca3af] border-[#e5e7eb]'
                    }`}>
                      {task ? 'Running' : 'Idle'}
                    </span>
                  </div>
                );
              })}
            </div>

            {failed > 0 && (
              <div className="mx-5 mb-4 mt-2 flex items-center gap-2 p-3 bg-[#fef2f2] border border-[#fecaca] rounded-lg">
                <AlertTriangle className="w-4 h-4 text-[#ef4444] flex-shrink-0" />
                <span className="text-xs text-[#dc2626]">{failed} pipeline{failed > 1 ? 's' : ''} failed — </span>
                <button onClick={() => navigate('/pipelines')} className="text-xs text-[#dc2626] underline hover:text-[#b91c1c]">view</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
