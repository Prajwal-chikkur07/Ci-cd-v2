import { CheckCircle, XCircle, Clock, Trash2, Loader2, Play } from 'lucide-react';
import { deletePipeline } from '../api/client';
import { usePipelineContext } from '../context/PipelineContext';
import { useParallelExecution } from '../hooks/useParallelExecution';
import type { HistoryEntry } from '../types/pipeline';

function extractRepoName(url: string): string {
  try {
    const parts = url.replace(/\.git$/, '').split('/');
    return parts[parts.length - 1] || url;
  } catch {
    return url;
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function ExecutionHistory() {
  const { executionHistory, loadFromHistory, removeFromHistory, activeExecutions, switchToExecution } = usePipelineContext();
  const { launchExecution } = useParallelExecution();

  const handleDelete = async (e: React.MouseEvent, entry: HistoryEntry) => {
    e.stopPropagation();
    try {
      await deletePipeline(entry.pipeline.pipeline_id);
      removeFromHistory(entry.pipeline.pipeline_id);
    } catch {
      // silently ignore
    }
  };

  const handleReExecute = (e: React.MouseEvent, entry: HistoryEntry) => {
    e.stopPropagation();
    launchExecution(entry.pipeline);
  };

  const activeIds = new Set(activeExecutions.keys());

  return (
    <div className="px-4">
      {/* Active Executions */}
      {activeExecutions.size > 0 && (
        <>
          <h3 className="text-xs font-semibold text-emerald-300/70 uppercase tracking-wider px-1 mb-2">
            Running ({activeExecutions.size})
          </h3>
          <div className="space-y-1 mb-4">
            {Array.from(activeExecutions.entries()).map(([pid, exec]) => {
              const total = exec.pipeline.stages.length;
              const completed = Array.from(exec.stageStatuses.values()).filter(
                (s) => s === 'success' || s === 'skipped',
              ).length;
              const failed = Array.from(exec.stageStatuses.values()).filter((s) => s === 'failed').length;
              const pct = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;

              return (
                <button
                  key={pid}
                  onClick={() => switchToExecution(pid)}
                  className="w-full text-left px-3 py-2.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors border border-emerald-500/20"
                >
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-emerald-400 animate-spin flex-shrink-0" />
                    <span className="text-sm text-white truncate font-medium">
                      {exec.pipeline.name || extractRepoName(exec.pipeline.repo_url)}
                    </span>
                  </div>
                  <div className="ml-6 mt-1">
                    <div className="flex justify-between text-[10px] text-emerald-300/60 mb-0.5">
                      <span>{completed}/{total} stages</span>
                      {failed > 0 && <span className="text-red-400">{failed} failed</span>}
                    </div>
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-400 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* History */}
      <h3 className="text-xs font-semibold text-blue-200/50 uppercase tracking-wider px-1 mb-2">
        History
      </h3>

      {executionHistory.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-blue-200/30">
          <Clock className="w-8 h-8 mb-2" />
          <p className="text-xs">No runs yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {executionHistory.map((entry: HistoryEntry, i: number) => {
            const isRunning = activeIds.has(entry.pipeline.pipeline_id);
            return (
              <div
                key={i}
                className="flex items-center rounded-lg hover:bg-white/10 transition-colors group"
              >
                <button
                  onClick={() => isRunning ? switchToExecution(entry.pipeline.pipeline_id) : loadFromHistory(entry)}
                  className="flex-1 text-left px-3 py-2.5 min-w-0"
                >
                  <div className="flex items-center gap-2">
                    {isRunning ? (
                      <Loader2 className="w-4 h-4 text-emerald-400 animate-spin flex-shrink-0" />
                    ) : entry.overallStatus === 'success' ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    )}
                    <span className="text-sm text-white truncate font-medium">
                      {entry.pipeline.name || extractRepoName(entry.pipeline.repo_url)}
                    </span>
                  </div>
                  <div className="ml-6 mt-0.5 flex items-center gap-2">
                    <span className="text-xs text-blue-200/50 truncate flex-1">
                      {entry.pipeline.goal}
                    </span>
                    <span className="text-[10px] text-blue-200/40 flex-shrink-0">
                      {isRunning ? 'Running...' : formatTime(entry.completedAt)}
                    </span>
                  </div>
                </button>
                {!isRunning && (
                  <div className="flex items-center mr-1 opacity-0 group-hover:opacity-100 transition-all">
                    <button
                      onClick={(e) => handleReExecute(e, entry)}
                      className="p-2 hover:bg-emerald-500/20 rounded-md transition-all"
                      title="Re-execute pipeline"
                    >
                      <Play className="w-3.5 h-3.5 text-emerald-400" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(e, entry)}
                      className="p-2 hover:bg-red-500/20 rounded-md transition-all"
                      title="Delete pipeline"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-red-400" />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
