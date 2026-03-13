import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';

function extractRepoName(url: string): string {
  try {
    const parts = url.replace(/\.git$/, '').split('/');
    return parts[parts.length - 1] || url;
  } catch {
    return url;
  }
}

export default function ActiveExecutionTabs() {
  const { activeExecutions, currentPipeline, switchToExecution } = usePipelineContext();

  if (activeExecutions.size <= 1) return null;

  return (
    <div className="bg-gray-900 border-b border-gray-700 px-4 py-1.5 flex items-center gap-1 flex-shrink-0 overflow-x-auto">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider mr-2 flex-shrink-0">
        Running:
      </span>
      {Array.from(activeExecutions.entries()).map(([pid, exec]) => {
        const isActive = currentPipeline?.pipeline_id === pid;
        const total = exec.pipeline.stages.length;
        const completed = Array.from(exec.stageStatuses.values()).filter(
          (s) => s === 'success' || s === 'skipped',
        ).length;
        const failed = Array.from(exec.stageStatuses.values()).filter((s) => s === 'failed').length;
        const allDone = (completed + failed) === total && total > 0;

        return (
          <button
            key={pid}
            onClick={() => switchToExecution(pid)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors flex-shrink-0 ${
              isActive
                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300 border border-transparent'
            }`}
          >
            {allDone ? (
              failed > 0 ? (
                <XCircle className="w-3 h-3 text-red-400" />
              ) : (
                <CheckCircle className="w-3 h-3 text-emerald-400" />
              )
            ) : (
              <Loader2 className="w-3 h-3 animate-spin" />
            )}
            <span className="truncate max-w-[120px]">
              {exec.pipeline.name || extractRepoName(exec.pipeline.repo_url)}
            </span>
            <span className="text-[10px] opacity-60">
              {completed}/{total}
            </span>
          </button>
        );
      })}
    </div>
  );
}
