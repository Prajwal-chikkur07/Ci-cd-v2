import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();

  if (activeExecutions.size <= 1) return null;

  const handleSwitch = (pid: string) => {
    switchToExecution(pid);
    navigate(`/pipeline/${pid}`);
  };

  return (
    <div className="bg-white border-b border-[#e5e7eb] px-4 py-1.5 flex items-center gap-1 flex-shrink-0 overflow-x-auto">
      <span className="text-[10px] text-[#9ca3af] uppercase tracking-wider mr-2 flex-shrink-0">Running:</span>
      {Array.from(activeExecutions.entries()).map(([pid, exec]) => {
        const isActive = currentPipeline?.pipeline_id === pid;
        const total = exec.pipeline.stages.length;
        const completed = Array.from(exec.stageStatuses.values()).filter(s => s === 'success' || s === 'skipped').length;
        const failed = Array.from(exec.stageStatuses.values()).filter(s => s === 'failed').length;
        const allDone = (completed + failed) === total && total > 0;
        return (
          <button key={pid} onClick={() => handleSwitch(pid)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors flex-shrink-0 border ${
              isActive ? 'bg-[#111827] text-white border-[#111827]' : 'bg-white text-[#6b7280] hover:bg-[#f3f4f6] border-[#e5e7eb]'
            }`}>
            {allDone ? (failed > 0 ? <XCircle className="w-3 h-3 text-[#ef4444]" /> : <CheckCircle className="w-3 h-3 text-[#22c55e]" />) : <Loader2 className="w-3 h-3 animate-spin" />}
            <span className="truncate max-w-[120px]">{exec.pipeline.name || extractRepoName(exec.pipeline.repo_url)}</span>
            <span className="text-[10px] opacity-60">{completed}/{total}</span>
          </button>
        );
      })}
    </div>
  );
}
