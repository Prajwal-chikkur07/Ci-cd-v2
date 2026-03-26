import { Hammer, FlaskConical, Shield, Rocket, Activity, CheckCircle, Clock } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { agentColors } from '../utils/statusColors';
import type { AgentType } from '../types/pipeline';

const agentMeta: Record<AgentType, {
  icon: React.ReactNode;
  description: string;
  responsibilities: string[];
}> = {
  build: {
    icon: <Hammer className="w-5 h-5" />,
    description: 'Compiles source code, resolves dependencies, and produces build artifacts.',
    responsibilities: ['Install dependencies', 'Compile code', 'Package artifacts', 'Cache builds'],
  },
  test: {
    icon: <FlaskConical className="w-5 h-5" />,
    description: 'Runs unit tests, integration tests, and generates coverage reports.',
    responsibilities: ['Unit tests', 'Integration tests', 'Coverage reports', 'Test fixtures'],
  },
  security: {
    icon: <Shield className="w-5 h-5" />,
    description: 'Scans for vulnerabilities, audits dependencies, and enforces security policies.',
    responsibilities: ['Dependency audit', 'SAST scanning', 'License checks', 'CVE detection'],
  },
  deploy: {
    icon: <Rocket className="w-5 h-5" />,
    description: 'Deploys applications to target environments using configured deployment strategies.',
    responsibilities: ['Container builds', 'Cloud deployments', 'Blue/green deploys', 'Rollbacks'],
  },
  verify: {
    icon: <Activity className="w-5 h-5" />,
    description: 'Verifies deployments are healthy and running correctly via health checks.',
    responsibilities: ['Health checks', 'Smoke tests', 'Port verification', 'Response validation'],
  },
};

const ALL_AGENTS: AgentType[] = ['build', 'test', 'security', 'deploy', 'verify'];

export default function AgentsPage() {
  const { currentPipeline, stageStatuses, executionHistory } = usePipelineContext();

  // Compute per-agent stats from history
  const agentStats: Record<AgentType, { total: number; success: number; lastRun?: string }> = {
    build: { total: 0, success: 0 }, test: { total: 0, success: 0 },
    security: { total: 0, success: 0 }, deploy: { total: 0, success: 0 }, verify: { total: 0, success: 0 },
  };

  for (const entry of executionHistory) {
    if (!entry.results) continue;
    for (const stage of entry.pipeline.stages) {
      const result = entry.results[stage.id];
      if (!result) continue;
      agentStats[stage.agent].total++;
      if (result.status === 'success') agentStats[stage.agent].success++;
      if (!agentStats[stage.agent].lastRun) agentStats[stage.agent].lastRun = entry.completedAt;
    }
  }

  // Current running status
  const agentRunning: Record<AgentType, string | null> = { build: null, test: null, security: null, deploy: null, verify: null };
  if (currentPipeline) {
    for (const stage of currentPipeline.stages) {
      if (stageStatuses.get(stage.id) === 'running') agentRunning[stage.agent] = stage.id;
    }
  }

  const totalTasks = Object.values(agentStats).reduce((s, a) => s + a.total, 0);
  const activeCount = Object.values(agentRunning).filter(Boolean).length;
  const avgSuccess = totalTasks > 0
    ? Math.round(Object.values(agentStats).reduce((s, a) => s + (a.total > 0 ? a.success / a.total : 0), 0) / 5 * 100)
    : 0;

  return (
    <div className="p-6 h-full overflow-y-auto">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Active Agents', value: activeCount, color: '#10a37f' },
          { label: 'Avg Success Rate', value: `${avgSuccess}%`, color: '#60a5fa' },
          { label: 'Total Tasks', value: totalTasks, color: '#9ca3af' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div className="text-xs text-[#4b5563] mb-1">{label}</div>
            <div className="text-2xl font-bold" style={{ color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Agent cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {ALL_AGENTS.map(agent => {
          const color = agentColors[agent];
          const meta = agentMeta[agent];
          const stats = agentStats[agent];
          const running = agentRunning[agent];
          const successRate = stats.total > 0 ? Math.round((stats.success / stats.total) * 100) : 0;

          return (
            <div key={agent} className={`bg-[#111827] border rounded-xl p-5 transition-all ${
              running ? 'border-accent/40 shadow-lg shadow-accent/5' : 'border-[#1f2937]'
            }`}>
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: color.color + '15', color: color.color }}>
                    {meta.icon}
                  </div>
                  <div>
                    <div className="font-semibold text-white">{color.label}</div>
                    <div className={`text-xs font-medium mt-0.5 flex items-center gap-1 ${running ? 'text-accent' : 'text-[#4b5563]'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${running ? 'bg-accent animate-pulse' : 'bg-[#374151]'}`} />
                      {running ? `Running: ${running}` : 'Idle'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-[#6b7280] mb-4 leading-relaxed">{meta.description}</p>

              {/* Responsibilities */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                {meta.responsibilities.map(r => (
                  <span key={r} className="text-[10px] px-2 py-0.5 rounded-full bg-[#1f2937] text-[#6b7280] border border-[#374151]">{r}</span>
                ))}
              </div>

              {/* Success rate bar */}
              <div className="mb-3">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-[#4b5563]">Success Rate</span>
                  <span style={{ color: color.color }}>{successRate}%</span>
                </div>
                <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${successRate}%`, backgroundColor: color.color }} />
                </div>
              </div>

              {/* Footer stats */}
              <div className="flex items-center justify-between text-xs text-[#4b5563]">
                <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-accent" />{stats.total} tasks</span>
                {stats.lastRun && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(stats.lastRun).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
