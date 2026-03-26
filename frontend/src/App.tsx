import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { usePipelineContext } from './context/PipelineContext';
import Layout from './components/Layout';
import CreatePipeline from './components/CreatePipeline';
import EditPipeline from './components/EditPipeline';
import PipelineDAG from './components/PipelineDAG';
import ExecutionControls from './components/ExecutionControls';
import StageDetailPanel from './components/StageDetailPanel';
import StatusBanner from './components/StatusBanner';
import ExecutionLog from './components/ExecutionLog';
import ActiveExecutionTabs from './components/ActiveExecutionTabs';
import AgentActivity from './components/AgentActivity';
import { agentColors } from './utils/statusColors';
import { getPipeline } from './api/client';

function PipelineInfo() {
  const { currentPipeline } = usePipelineContext();
  if (!currentPipeline) return null;

  const { analysis } = currentPipeline;

  return (
    <div className="bg-[#111827] border-b border-[#1f2937] px-5 py-3 flex items-center gap-4 flex-shrink-0">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        {currentPipeline.name && (
          <>
            <div className="min-w-0">
              <div className="text-[10px] text-[#4b5563] mb-0.5 uppercase tracking-wide">Name</div>
              <div className="text-sm font-semibold text-white truncate">{currentPipeline.name}</div>
            </div>
            <div className="h-6 w-px bg-[#1f2937]" />
          </>
        )}
        <div className="min-w-0">
          <div className="text-[10px] text-[#4b5563] mb-0.5 uppercase tracking-wide">Goal</div>
          <div className="text-sm text-[#e2e8f0] truncate">{currentPipeline.goal}</div>
        </div>
        <div className="h-6 w-px bg-[#1f2937]" />
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#1f2937] text-xs text-[#9ca3af] border border-[#374151]">
            {analysis.language}
          </span>
          {analysis.framework && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-accent/10 text-xs text-accent border border-accent/20">
              {analysis.framework}
            </span>
          )}
          {analysis.has_dockerfile && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#1f2937] text-xs text-[#60a5fa] border border-[#374151]">
              Docker
            </span>
          )}
        </div>
        <div className="h-6 w-px bg-[#1f2937]" />
        <div className="flex items-center gap-1.5">
          {currentPipeline.stages.map((s) => (
            <div
              key={s.id}
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: agentColors[s.agent].color }}
              title={`${s.id} (${s.agent})`}
            />
          ))}
          <span className="text-xs text-[#4b5563] ml-1">{currentPipeline.stages.length} stages</span>
        </div>
      </div>
    </div>
  );
}

function PipelineView() {
  const { currentPipeline, isRegenerating, isEditing, executionLogs, isExecuting, executionHistory, loadFromHistory, historyLoaded, setPipeline } = usePipelineContext();
  const { pipelineId } = useParams<{ pipelineId: string }>();
  const navigate = useNavigate();
  const [logsManuallyHidden, setLogsManuallyHidden] = useState(false);
  const [loadingPipeline, setLoadingPipeline] = useState(false);

  // On refresh: wait for history to load, then restore pipeline from history or fetch directly
  useEffect(() => {
    if (!pipelineId || !historyLoaded) return;
    if (currentPipeline?.pipeline_id === pipelineId) return;

    const entry = executionHistory.find(e => e.pipeline.pipeline_id === pipelineId);
    if (entry) {
      loadFromHistory(entry);
      return;
    }

    // Not in history yet — fetch directly from API
    setLoadingPipeline(true);
    getPipeline(pipelineId).then((spec) => {
      setPipeline(spec);
    }).catch(() => {
      navigate('/', { replace: true });
    }).finally(() => setLoadingPipeline(false));
  }, [pipelineId, historyLoaded, executionHistory]);

  const handleToggleLogs = () => setLogsManuallyHidden(prev => !prev);

  useEffect(() => { if (isExecuting) setLogsManuallyHidden(false); }, [isExecuting]);
  useEffect(() => { if (executionLogs.length > 0) setLogsManuallyHidden(false); }, [currentPipeline?.pipeline_id]);

  if (isRegenerating && currentPipeline) {
    return (
      <Layout>
        <div className="h-full overflow-y-auto">
          <CreatePipeline prefill={{ repoUrl: currentPipeline.repo_url, goal: currentPipeline.goal, name: currentPipeline.name, useDocker: false }} />
        </div>
      </Layout>
    );
  }

  if (isEditing && currentPipeline) {
    return (
      <Layout>
        <div className="h-full overflow-y-auto"><EditPipeline /></div>
      </Layout>
    );
  }

  if (!currentPipeline) {
    // Still loading — don't redirect yet
    if (!historyLoaded || loadingPipeline) {
      return (
        <Layout>
          <div className="flex items-center justify-center h-full text-[#4b5563] text-sm gap-2">
            <span className="w-4 h-4 border-2 border-[#374151] border-t-accent rounded-full animate-spin" />
            Loading pipeline...
          </div>
        </Layout>
      );
    }
    navigate('/', { replace: true });
    return null;
  }

  const hasLogs = executionLogs.length > 0;
  const logsVisible = logsManuallyHidden ? false : (hasLogs || isExecuting);

  return (
    <Layout>
      <div className="flex flex-col h-full bg-[#0f172a]">
        <ActiveExecutionTabs />
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Center: DAG + controls */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <PipelineInfo />
            <ExecutionControls onToggleLogs={handleToggleLogs} showLogs={logsVisible} />
            <StatusBanner />
            <div className="flex-1 overflow-hidden relative">
              <PipelineDAG />
              <StageDetailPanel />
            </div>
          </div>
          {/* Right: Agent Activity */}
          <div className="p-4 overflow-y-auto border-l border-[#1f2937] bg-[#0f172a]">
            <AgentActivity />
          </div>
          {/* Far right: Execution Log */}
          {logsVisible && <ExecutionLog />}
        </div>
      </div>
    </Layout>
  );
}

function NewPipelinePage() {
  return (
    <Layout>
      <div className="h-full overflow-y-auto">
        <CreatePipeline />
      </div>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<NewPipelinePage />} />
      <Route path="/pipeline/:pipelineId" element={<PipelineView />} />
      <Route path="*" element={<NewPipelinePage />} />
    </Routes>
  );
}
