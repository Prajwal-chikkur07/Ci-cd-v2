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
import { agentColors } from './utils/statusColors';
import { getPipeline } from './api/client';

function PipelineInfo() {
  const { currentPipeline } = usePipelineContext();
  if (!currentPipeline) return null;

  const { analysis } = currentPipeline;

  return (
    <div className="bg-white border-b border-gray-200 px-5 py-3 flex items-center gap-6 flex-shrink-0">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        {currentPipeline.name && (
          <>
            <div className="min-w-0">
              <div className="text-xs text-gray-400 mb-0.5">Name</div>
              <div className="text-sm font-semibold text-gray-900 truncate">{currentPipeline.name}</div>
            </div>
            <div className="h-8 w-px bg-gray-200" />
          </>
        )}
        <div className="min-w-0">
          <div className="text-xs text-gray-400 mb-0.5">Goal</div>
          <div className="text-sm font-medium text-gray-800 truncate">{currentPipeline.goal}</div>
        </div>
        <div className="h-8 w-px bg-gray-200" />
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-gray-100 text-xs font-medium text-gray-700">
            {analysis.language}
          </span>
          {analysis.framework && (
            <span className="inline-flex items-center px-2 py-1 rounded-md bg-blue-50 text-xs font-medium text-blue-700">
              {analysis.framework}
            </span>
          )}
          <span className="inline-flex items-center px-2 py-1 rounded-md bg-gray-50 text-xs text-gray-500">
            {analysis.package_manager}
          </span>
          {analysis.has_dockerfile && (
            <span className="inline-flex items-center px-2 py-1 rounded-md bg-cyan-50 text-xs text-cyan-700">
              Docker
            </span>
          )}
        </div>
        <div className="h-8 w-px bg-gray-200" />
        <div className="flex items-center gap-1.5">
          {currentPipeline.stages.map((s) => (
            <div
              key={s.id}
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: agentColors[s.agent].color }}
              title={`${s.id} (${s.agent})`}
            />
          ))}
          <span className="text-xs text-gray-400 ml-1">{currentPipeline.stages.length} stages</span>
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
          <div className="flex items-center justify-center h-full text-gray-400 text-sm gap-2">
            <span className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
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
      <div className="flex flex-col h-full">
        <ActiveExecutionTabs />
        <div className="flex flex-1 min-h-0">
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            <PipelineInfo />
            <ExecutionControls onToggleLogs={handleToggleLogs} showLogs={logsVisible} />
            <StatusBanner />
            <PipelineDAG />
            <StageDetailPanel />
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
      <Route path="/" element={<NewPipelinePage />} />
      <Route path="/pipeline/:pipelineId" element={<PipelineView />} />
      <Route path="*" element={<NewPipelinePage />} />
    </Routes>
  );
}
