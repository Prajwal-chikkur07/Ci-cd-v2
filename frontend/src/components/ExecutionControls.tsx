import { useEffect, useState, useCallback, useRef } from 'react';
import type { LogEntry } from '../types/pipeline';
import { Play, Loader2, CheckCircle, XCircle, RefreshCw, Pencil, ScrollText } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { usePipeline } from '../hooks/usePipeline';
import { useWebSocket } from '../hooks/useWebSocket';
import type { StageUpdate } from '../types/pipeline';

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
    // Parallel execution
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
  // Track which pipeline ID the current execution is for (to update the right active execution)
  const executingPipelineId = useRef<string | null>(null);
  // Collect logs in a ref so they're always available for history
  const collectedLogsRef = useRef<LogEntry[]>([]);
  // Track whether WS already finalized execution (pipeline_done received before HTTP response)
  const wsFinalizedRef = useRef(false);

  const onWsUpdate = useCallback((update: StageUpdate) => {
    const pid = executingPipelineId.current;

    // Update the main view (current pipeline)
    if (update.stage_id) {
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
    }
    if (update.log_type && update.log_message) {
      const logEntry = {
        timestamp: new Date().toISOString(),
        stage_id: update.stage_id || undefined,
        type: update.log_type,
        message: update.log_message,
        details: update.log_tail,
      };
      addLog(logEntry);
      collectedLogsRef.current.push(logEntry);

      // Also update the parallel execution tracker
      if (pid) {
        addExecutionLog(pid, logEntry);
      }
    }

    // When pipeline_done arrives via WS, stop execution immediately
    // This ensures the UI updates even if the HTTP response is slow
    if (update.log_type === 'pipeline_done') {
      wsFinalizedRef.current = true;
      setWsActive(false);
      stopExecution();
      if (pid) {
        unregisterExecution(pid);
      }
      executingPipelineId.current = null;
    }

    // Update parallel execution tracker
    if (pid) {
      if (update.stage_id) {
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

  // Elapsed timer
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

    // Reset all statuses to pending
    for (const stage of currentPipeline.stages) {
      updateStageStatus(stage.id, 'pending');
    }

    clearLogs();
    collectedLogsRef.current = [];
    startExecution();
    setElapsed(0);
    setPipelineIdForWs(pid);
    setWsActive(true);

    // Register as active parallel execution
    registerExecution(pid, currentPipeline);

    const results = await execute(pid);

    // Only clean up if WS pipeline_done hasn't already done it
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
      });
    } else if (wsFinalizedRef.current) {
      // HTTP failed but WS completed — add history from WS-collected logs
      addToHistory({
        pipeline: currentPipeline,
        results: null,
        completedAt: new Date().toISOString(),
        overallStatus: 'failed',
        logs: collectedLogsRef.current,
      });
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

  return (
    <div className="bg-white border-b border-gray-200 px-5 py-3 flex items-center gap-3 flex-shrink-0">
      {/* Execute button */}
      <button
        onClick={handleExecute}
        disabled={isExecuting || loading}
        className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
      >
        {isExecuting || loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Executing...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Execute Pipeline
          </>
        )}
      </button>

      {/* Regenerate button */}
      <button
        onClick={startRegenerate}
        disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 disabled:bg-gray-100 disabled:text-gray-400 text-blue-700 text-sm font-medium rounded-lg transition-colors"
        title="Re-analyze repo and generate a new pipeline"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Regenerate
      </button>

      {/* Edit button */}
      <button
        onClick={startEditing}
        disabled={isExecuting || loading}
        className="flex items-center gap-1.5 px-3 py-2 bg-amber-50 hover:bg-amber-100 disabled:bg-gray-100 disabled:text-gray-400 text-amber-700 text-sm font-medium rounded-lg transition-colors"
        title="Edit stage commands and settings"
      >
        <Pencil className="w-3.5 h-3.5" />
        Edit
      </button>

      {/* Logs toggle button */}
      <button
        onClick={onToggleLogs}
        className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
          showLogs
            ? 'bg-purple-100 text-purple-700'
            : 'bg-gray-50 hover:bg-gray-100 text-gray-600'
        }`}
        title={showLogs ? 'Hide execution logs' : 'Show execution logs'}
      >
        <ScrollText className="w-3.5 h-3.5" />
        Logs
        {executionLogs.length > 0 && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
            showLogs ? 'bg-purple-200 text-purple-800' : 'bg-gray-200 text-gray-600'
          }`}>
            {executionLogs.length}
          </span>
        )}
      </button>

      {/* Progress */}
      <div className="flex-1 flex items-center gap-3">
        <div className="flex-1 max-w-xs">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{completed}/{total} stages complete</span>
            {isExecuting && <span className="font-mono">{elapsed.toFixed(1)}s</span>}
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Status banner */}
        {allDone && (
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium ${
              pipelineSuccess
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {pipelineSuccess ? (
              <>
                <CheckCircle className="w-4 h-4" />
                Pipeline Succeeded
              </>
            ) : (
              <>
                <XCircle className="w-4 h-4" />
                Pipeline Failed
              </>
            )}
          </div>
        )}
      </div>

      {error && (
        <span className="text-sm text-red-600">{error}</span>
      )}
    </div>
  );
}
