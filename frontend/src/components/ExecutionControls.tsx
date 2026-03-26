import { useEffect, useState, useCallback, useRef } from 'react';
import type { LogEntry } from '../types/pipeline';
import { Play, Loader2, CheckCircle, XCircle, RefreshCw, Pencil, ScrollText, RotateCcw, Link2 } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { usePipeline } from '../hooks/usePipeline';
import { useWebSocket } from '../hooks/useWebSocket';
import type { StageUpdate } from '../types/pipeline';
import { executeFailedStages, chainPipelines } from '../api/client';

interface ExecutionControlsProps {
  onToggleLogs?: () => void;
  showLogs?: boolean;
}

export default function ExecutionControls({ onToggleLogs, showLogs }: ExecutionControlsProps) {
  const {
    currentPipeline,
    stageStatuses,
    isExecuting,
    startExecution,
    stopExecution,
    updateStageStatus,
    setBulkResults,
    addToHistory,
    setRecoveryPlan,
    startRegenerate,
    startEditing,
    addLog,
    clearLogs,
    executionLogs,
    setDeployUrl,
    deployUrl,
    executionHistory,
    registerExecution,
    unregisterExecution,
    updateExecutionStageStatus,
    addExecutionLog,
    setExecutionRecoveryPlan,
    setExecutionBulkResults,
  } = usePipelineContext();

  const { loading, error, execute } = usePipeline();
  const [elapsed, setElapsed] = useState(0);
  const [wsActive, setWsActive] = useState(false);
  const [pipelineIdForWs, setPipelineIdForWs] = useState<string | null>(null);
  const [rerunLoading, setRerunLoading] = useState(false);
  const [chainLoading, setChainLoading] = useState(false);
  const [chainError, setChainError] = useState<string | null>(null);
  const executingPipelineId = useRef<string | null>(null);
  const lastDeployUrlRef = useRef<string | null>(null);
  const collectedLogsRef = useRef<LogEntry[]>([]);
  const wsFinalizedRef = useRef(false);
  const startTimeRef = useRef<number>(0);

  // Feature 5: Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const onWsUpdate = useCallback((update: StageUpdate) => {
    const pid = executingPipelineId.current;

    if (update.stage_id && update.log_type !== 'stage_output') {
      updateStageStatus(update.stage_id, update.status);
    }
    if (update.recovery_strategy) {
      setRecoveryPlan(update.stage_id, {
        strategy: update.recovery_strategy,
        reason: update.recovery_reason ?? '',
        modified_command: update.modified_command,
      });
    }
    if (update.deploy_url) {
      setDeployUrl(update.deploy_url);
      lastDeployUrlRef.current = update.deploy_url;
    }
    if (update.log_type && update.log_message) {
      const logEntry: LogEntry = {
        timestamp: new Date().toISOString(),
        stage_id: update.stage_id || undefined,
        type: update.log_type,
        message: update.log_message,
        details: update.log_tail,
      };
      addLog(logEntry);
      collectedLogsRef.current.push(logEntry);
      if (pid) addExecutionLog(pid, logEntry);
    }

    if (update.log_type === 'pipeline_done') {
      wsFinalizedRef.current = true;
      setWsActive(false);
      stopExecution();
      if (pid) unregisterExecution(pid);
      executingPipelineId.current = null;

      // Feature 5: Browser notification
      if ('Notification' in window && Notification.permission === 'granted') {
        const duration = ((Date.now() - startTimeRef.current) / 1000).toFixed(1);
        const succeeded = update.log_message?.includes('success') ?? false;
        new Notification(succeeded ? '✅ Pipeline Succeeded' : '❌ Pipeline Failed', {
          body: `${update.log_message ?? ''} (${duration}s)`,
          icon: '/favicon.ico',
        });
      }

      // Feature 10: Auto-open deploy URL on success
      const succeeded = update.log_message?.includes('success') ?? false;
      if (succeeded && lastDeployUrlRef.current) {
        window.open(lastDeployUrlRef.current, '_blank');
      }
    }

    if (pid) {
      if (update.stage_id && update.log_type !== 'stage_output') {
        updateExecutionStageStatus(pid, update.stage_id, update.status);
      }
      if (update.recovery_strategy) {
        setExecutionRecoveryPlan(pid, update.stage_id, {
          strategy: update.recovery_strategy,
          reason: update.recovery_reason ?? '',
          modified_command: update.modified_command,
        });
      }
    }
  }, [updateStageStatus, setRecoveryPlan, addLog, setDeployUrl, stopExecution, unregisterExecution, addExecutionLog, updateExecutionStageStatus, setExecutionRecoveryPlan]);

  useWebSocket(wsActive ? pipelineIdForWs : null, onWsUpdate);

  useEffect(() => {
    if (!isExecuting) return;
    const start = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - start) / 1000), 100);
    return () => clearInterval(timer);
  }, [isExecuting]);

  const handleExecute = async () => {
    if (!currentPipeline) return;
    const pid = currentPipeline.pipeline_id;
    executingPipelineId.current = pid;
    wsFinalizedRef.current = false;
    startTimeRef.current = Date.now();

    for (const stage of currentPipeline.stages) {
      updateStageStatus(stage.id, 'pending');
    }
    clearLogs();
    collectedLogsRef.current = [];
    lastDeployUrlRef.current = null;
    setDeployUrl(null);
    startExecution();
    setElapsed(0);
    setPipelineIdForWs(pid);
    setWsActive(true);
    registerExecution(pid, currentPipeline);

    const results = await execute(pid);

    if (!wsFinalizedRef.current) {
      setWsActive(false);
      stopExecution();
      executingPipelineId.current = null;
      unregisterExecution(pid);
    }

    if (results) {
      setBulkResults(results);
      setExecutionBulkResults(pid, results);
      const hasFailed = Object.values(results).some((r) => r.status === 'failed');
      addToHistory({
        pipeline: currentPipeline,
        results,
        completedAt: new Date().toISOString(),
        overallStatus: hasFailed ? 'failed' : 'success',
        logs: collectedLogsRef.current,
        duration_seconds: (Date.now() - startTimeRef.current) / 1000,
      });
    } else if (wsFinalizedRef.current) {
      addToHistory({
        pipeline: currentPipeline,
        results: null,
        completedAt: new Date().toISOString(),
        overallStatus: 'failed',
        logs: collectedLogsRef.current,
        duration_seconds: (Date.now() - startTimeRef.current) / 1000,
      });
    }
  };

  // Feature 7: Re-run failed stages only
  const handleRerunFailed = async () => {
    if (!currentPipeline) return;
    const pid = currentPipeline.pipeline_id;
    setRerunLoading(true);
    executingPipelineId.current = pid;
    wsFinalizedRef.current = false;
    lastDeployUrlRef.current = null;
    setDeployUrl(null);
    startTimeRef.current = Date.now();

    clearLogs();
    collectedLogsRef.current = [];
    startExecution();
    setElapsed(0);
    setPipelineIdForWs(pid);
    setWsActive(true);
    registerExecution(pid, currentPipeline);

    try {
      const results = await executeFailedStages(pid);
      if (!wsFinalizedRef.current) {
        setWsActive(false);
        stopExecution();
        executingPipelineId.current = null;
        unregisterExecution(pid);
      }
      if (results) {
        setBulkResults(results as Record<string, import('../types/pipeline').StageResult>);
        const hasFailed = Object.values(results).some((r: unknown) => (r as { status: string }).status === 'failed');
        addToHistory({
          pipeline: currentPipeline,
          results: results as Record<string, import('../types/pipeline').StageResult>,
          completedAt: new Date().toISOString(),
          overallStatus: hasFailed ? 'failed' : 'success',
          logs: collectedLogsRef.current,
          duration_seconds: (Date.now() - startTimeRef.current) / 1000,
        });
      }
    } catch (e) {
      setWsActive(false);
      stopExecution();
      executingPipelineId.current = null;
      unregisterExecution(pid);
    } finally {
      setRerunLoading(false);
    }
  };

  // Feature 9: Chain — run this pipeline then all others in history sequentially
  const handleChain = async () => {
    if (!currentPipeline) return;
    setChainError(null);
    const otherIds = executionHistory
      .filter((e) => e.pipeline.pipeline_id !== currentPipeline.pipeline_id)
      .map((e) => e.pipeline.pipeline_id);

    if (otherIds.length === 0) {
      setChainError('No other pipelines to chain. Create more pipelines first.');
      return;
    }

    setChainLoading(true);
    try {
      await chainPipelines(currentPipeline.pipeline_id, otherIds);
    } catch (e: unknown) {
      setChainError(e instanceof Error ? e.message : 'Chain failed');
    } finally {
      setChainLoading(false);
    }
  };

  if (!currentPipeline) return null;

  const total = currentPipeline.stages.length;
  const completed = Array.from(stageStatuses.values()).filter(
    (s) => s === 'success' || s === 'skipped',
  ).length;
  const failed = Array.from(stageStatuses.values()).filter((s) => s === 'failed').length;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const allDone = !isExecuting && (completed + failed === total) && total > 0 && (completed > 0 || failed > 0);
  const pipelineSuccess = allDone && failed === 0;
  const canRerunFailed = !isExecuting && !loading && failed > 0;

  return (
    <div className="bg-white border-b border-[#e5e7eb] px-5 py-3 flex flex-wrap items-center gap-2 flex-shrink-0">
      <button onClick={handleExecute} disabled={isExecuting || loading}
        className="flex items-center gap-2 px-4 py-2 bg-[#111827] hover:bg-[#1f2937] disabled:bg-[#e5e7eb] disabled:text-[#9ca3af] disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors">
        {isExecuting || loading ? <><Loader2 className="w-4 h-4 animate-spin" />Executing...</> : <><Play className="w-4 h-4" />Execute Pipeline</>}
      </button>

      {canRerunFailed && (
        <button onClick={handleRerunFailed} disabled={rerunLoading}
          className="flex items-center gap-1.5 px-3 py-2 bg-[#fffbeb] hover:bg-[#fef3c7] disabled:opacity-50 text-[#d97706] text-sm font-medium rounded-lg transition-colors border border-[#fde68a]">
          {rerunLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
          Re-run Failed ({failed})
        </button>
      )}

      <button onClick={startRegenerate} disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-[#f3f4f6] hover:bg-[#e5e7eb] disabled:opacity-50 text-[#374151] text-sm font-medium rounded-lg transition-colors border border-[#e5e7eb]">
        <RefreshCw className="w-3.5 h-3.5" />Regenerate
      </button>

      <button onClick={startEditing} disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-[#f3f4f6] hover:bg-[#e5e7eb] disabled:opacity-50 text-[#374151] text-sm font-medium rounded-lg transition-colors border border-[#e5e7eb]">
        <Pencil className="w-3.5 h-3.5" />Edit
      </button>

      {executionHistory.length > 1 && (
        <button onClick={handleChain} disabled={isExecuting || chainLoading}
          className="flex items-center gap-1.5 px-3 py-2 bg-[#f3f4f6] hover:bg-[#e5e7eb] disabled:opacity-50 text-[#374151] text-sm font-medium rounded-lg transition-colors border border-[#e5e7eb]">
          {chainLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
          Chain All
        </button>
      )}

      <button onClick={onToggleLogs}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors border ${
          showLogs ? 'bg-[#111827] text-white border-[#111827]' : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] text-[#374151] border-[#e5e7eb]'
        }`}>
        <ScrollText className="w-3.5 h-3.5" />
        Logs
        {executionLogs.length > 0 && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${showLogs ? 'bg-white/20 text-white' : 'bg-[#e5e7eb] text-[#6b7280]'}`}>
            {executionLogs.length}
          </span>
        )}
      </button>

      <div className="flex-1 flex items-center gap-3 min-w-0">
        <div className="flex-1 max-w-xs">
          <div className="flex justify-between text-xs text-[#6b7280] mb-1">
            <span>{completed}/{total} stages complete</span>
            {isExecuting && <span className="font-mono">{elapsed.toFixed(1)}s</span>}
          </div>
          <div className="h-1.5 bg-[#f3f4f6] rounded-full overflow-hidden">
            <div className="h-full bg-[#111827] rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {deployUrl && (
          <a href={deployUrl} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-[#16a34a] hover:text-[#15803d] font-medium truncate max-w-[160px]">
            🚀 {deployUrl}
          </a>
        )}

        {allDone && (
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border ${
            pipelineSuccess
              ? 'bg-[#f0fdf4] text-[#16a34a] border-[#bbf7d0]'
              : 'bg-[#fef2f2] text-[#dc2626] border-[#fecaca]'
          }`}>
            {pipelineSuccess ? <><CheckCircle className="w-4 h-4" />Pipeline Succeeded</> : <><XCircle className="w-4 h-4" />Pipeline Failed</>}
          </div>
        )}
      </div>

      {(error || chainError) && <span className="text-sm text-[#dc2626] w-full">{error || chainError}</span>}
    </div>
  );
}
