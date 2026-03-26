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
import DashboardPage from './pages/DashboardPage';
import PipelinesPage from './pages/PipelinesPage';
import AgentsPage from './pages/AgentsPage';
import LogsPage from './pages/LogsPage';
import SettingsPage from './pages/SettingsPage';
import { agentColors } from './utils/statusColors';
import { getPipeline } from './api/client';

function PipelineInfo() {
  const { currentPipeline } = usePipelineContext();
  if (!currentPipeline) return null;

  const { analysis } = currentPipeline;

  return (
    <div className="bg-white border-b border-[#e5e7eb] px-5 py-3 flex items-center gap-4 flex-shrink-0">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        {currentPipeline.name && (
          <>
            <div className="min-w-0">
              <div className="text-[10px] text-[#9ca3af] mb-0.5 uppercase tracking-wide">Name</div>
              <div className="text-sm font-semibold text-[#111827] truncate">{currentPipeline.name}</div>
            </div>
            <div className="h-6 w-px bg-[#e5e7eb]" />
          </>
        )}
        <div className="min-w-0">
          <div className="text-[10px] text-[#9ca3af] mb-0.5 uppercase tracking-wide">Goal</div>
          <div className="text-sm text-[#374151] truncate">{currentPipeline.goal}</div>
        </div>
        <div className="h-6 w-px bg-[#e5e7eb]" />
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#f3f4f6] text-xs text-[#374151] border border-[#e5e7eb]">
            {analysis.language}
          </span>
          {analysis.framework && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#f3f4f6] text-xs text-[#374151] border border-[#e5e7eb]">
              {analysis.framework}
            </span>
          )}
          {analysis.has_dockerfile && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-[#eff6ff] text-xs text-[#2563eb] border border-[#bfdbfe]">
              Docker
            </span>
          )}
        </div>
        <div className="h-6 w-px bg-[#e5e7eb]" />
        <div className="flex items-center gap-1.5">
          {currentPipeline.stages.map((s) => (
            <div key={s.id} className="w-2 h-2 rounded-full" style={{ backgroundColor: agentColors[s.agent].color }} title={`${s.id} (${s.agent})`} />
          ))}
          <span className="text-xs text-[#9ca3af] ml-1">{currentPipeline.stages.length} stages</span>
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
          <div className="flex items-center justify-center h-full text-[#6b7280] text-sm gap-2">
            <span className="w-4 h-4 border-2 border-[#e5e7eb] border-t-[#111827] rounded-full animate-spin" />
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
      <div className="flex flex-col h-full bg-[#f9fafb]">
        <ActiveExecutionTabs />
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <PipelineInfo />
            <ExecutionControls onToggleLogs={handleToggleLogs} showLogs={logsVisible} />
            <StatusBanner />
            <div className="flex-1 overflow-hidden relative min-h-0">
              <div className="absolute inset-0">
                <PipelineDAG />
              </div>
              <StageDetailPanel />
            </div>
          </div>
          <div className="p-4 overflow-y-auto border-l border-[#e5e7eb] bg-white">
            <AgentActivity />
          </div>
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
      <Route path="/" element={<Layout><DashboardPage /></Layout>} />
      <Route path="/pipeline/:pipelineId" element={<PipelineView />} />
      <Route path="/pipelines" element={<Layout><PipelinesPage /></Layout>} />
      <Route path="/agents" element={<Layout><AgentsPage /></Layout>} />
      <Route path="/logs" element={<Layout><LogsPage /></Layout>} />
      <Route path="/settings" element={<Layout><SettingsPage /></Layout>} />
      <Route path="*" element={<Layout><DashboardPage /></Layout>} />
    </Routes>
  );
}
