import { useCallback, useRef, useEffect } from 'react';
import { executePipeline, createWebSocketUrl } from '../api/client';
import { usePipelineContext } from '../context/PipelineContext';
import type { StageUpdate, PipelineSpec, StageResult, LogEntry } from '../types/pipeline';

/**
 * Hook to launch pipeline executions in the background.
 * Manages its own WebSocket connections per pipeline.
 */
export function useParallelExecution() {
  const {
    registerExecution,
    unregisterExecution,
    updateExecutionStageStatus,
    addExecutionLog,
    setExecutionRecoveryPlan,
    setExecutionBulkResults,
    addToHistory,
    activeExecutions,
  } = usePipelineContext();

  const wsRefs = useRef<Map<string, WebSocket>>(new Map());
  // Collect logs per pipeline in a ref so they're always up-to-date
  const logsRef = useRef<Map<string, LogEntry[]>>(new Map());

  // Clean up WebSockets on unmount
  useEffect(() => {
    return () => {
      for (const ws of wsRefs.current.values()) {
        ws.close();
      }
      wsRefs.current.clear();
    };
  }, []);

  const launchExecution = useCallback(async (pipeline: PipelineSpec) => {
    const pid = pipeline.pipeline_id;

    // Don't launch if already running
    if (activeExecutions.has(pid)) return;

    // Register in context
    registerExecution(pid, pipeline);
    logsRef.current.set(pid, []);

    // Connect WebSocket
    const wsUrl = createWebSocketUrl(pid);
    const ws = new WebSocket(wsUrl);
    wsRefs.current.set(pid, ws);

    ws.onmessage = (event) => {
      try {
        const update: StageUpdate = JSON.parse(event.data);
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
        if (update.log_type && update.log_message) {
          const logEntry: LogEntry = {
            timestamp: new Date().toISOString(),
            stage_id: update.stage_id || undefined,
            type: update.log_type,
            message: update.log_message,
            details: update.log_tail,
          };
          addExecutionLog(pid, logEntry);
          // Also collect in ref for history
          const logs = logsRef.current.get(pid);
          if (logs) logs.push(logEntry);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      wsRefs.current.delete(pid);
    };

    // Execute
    try {
      const results = await executePipeline(pid);
      // Close WebSocket
      ws.close();
      wsRefs.current.delete(pid);

      // Update results
      setExecutionBulkResults(pid, results);

      // Add to history with collected logs
      const hasFailed = Object.values(results).some((r: StageResult) => r.status === 'failed');
      const collectedLogs = logsRef.current.get(pid) || [];
      addToHistory({
        pipeline,
        results,
        completedAt: new Date().toISOString(),
        overallStatus: hasFailed ? 'failed' : 'success',
        logs: collectedLogs,
      });

      // Cleanup
      logsRef.current.delete(pid);
      unregisterExecution(pid);
    } catch (err) {
      ws.close();
      wsRefs.current.delete(pid);
      logsRef.current.delete(pid);
      unregisterExecution(pid);
    }
  }, [activeExecutions, registerExecution, unregisterExecution, updateExecutionStageStatus, addExecutionLog, setExecutionRecoveryPlan, setExecutionBulkResults, addToHistory]);

  return { launchExecution };
}
