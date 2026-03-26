import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2, Clock, GitBranch, Play, Trash2, Eye } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { deletePipeline } from '../api/client';
import { useParallelExecution } from '../hooks/useParallelExecution';
import type { HistoryEntry } from '../types/pipeline';

type Filter = 'all' | 'success' | 'failed' | 'running';

function extractRepoName(url: string) {
  try { return url.replace(/\.git$/, '').split('/').slice(-2).join('/'); }
  catch { return url; }
}

function formatDuration(s?: number | null) {
  if (!s) return '—';
  if (s < 60) return `${s.toFixed(0)}s`;
  return `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
}

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
}

const statusBadge: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  success: { label: 'Success', color: '#10a37f', bg: '#064e3b33', icon: <CheckCircle className="w-3 h-3" /> },
  failed:  { label: 'Failed',  color: '#ef4444', bg: '#7f1d1d22', icon: <XCircle className="w-3 h-3" /> },
  partial: { label: 'Partial', color: '#f59e0b', bg: '#78350f22', icon: <Clock className="w-3 h-3" /> },
  running: { label: 'Running', color: '#60a5fa', bg: '#1e3a5f33', icon: <Loader2 className="w-3 h-3 animate-spin" /> },
};

export default function PipelinesPage() {
  const { executionHistory, removeFromHistory, activeExecutions, loadFromHistory } = usePipelineContext();
  const { launchExecution } = useParallelExecution();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');

  const activeIds = new Set(activeExecutions.keys());

  const enriched = executionHistory.map(e => ({
    ...e,
    isRunning: activeIds.has(e.pipeline.pipeline_id),
    effectiveStatus: activeIds.has(e.pipeline.pipeline_id) ? 'running' : e.overallStatus,
  }));

  const filtered = enriched.filter(e => {
    if (filter === 'all') return true;
    if (filter === 'running') return e.isRunning;
    return e.effectiveStatus === filter;
  });

  const counts = {
    all: enriched.length,
    success: enriched.filter(e => e.effectiveStatus === 'success').length,
    failed: enriched.filter(e => e.effectiveStatus === 'failed').length,
    running: enriched.filter(e => e.isRunning).length,
  };

  const handleDelete = async (e: React.MouseEvent, entry: HistoryEntry) => {
    e.stopPropagation();
    await deletePipeline(entry.pipeline.pipeline_id).catch(() => {});
    removeFromHistory(entry.pipeline.pipeline_id);
  };

  const handleView = (entry: HistoryEntry) => {
    loadFromHistory(entry);
    navigate(`/pipeline/${entry.pipeline.pipeline_id}`);
  };

  return (
    <div className="p-6 h-full overflow-y-auto">
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Runs', value: counts.all, color: '#9ca3af' },
          { label: 'Successful', value: counts.success, color: '#10a37f' },
          { label: 'Failed', value: counts.failed, color: '#ef4444' },
          { label: 'Running', value: counts.running, color: '#60a5fa' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div className="text-xs text-[#4b5563] mb-1">{label}</div>
            <div className="text-2xl font-bold" style={{ color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 bg-[#111827] border border-[#1f2937] rounded-lg p-1 w-fit">
        {(['all', 'success', 'failed', 'running'] as Filter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
              filter === f ? 'bg-accent text-white' : 'text-[#4b5563] hover:text-[#9ca3af]'
            }`}
          >
            {f} {f !== 'all' && <span className="ml-1 text-xs opacity-60">({counts[f]})</span>}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1f2937]">
              {['Repository', 'Goal', 'Status', 'Duration', 'Date', 'Actions'].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[#4b5563] uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-[#374151] text-sm">No pipelines found</td></tr>
            ) : filtered.map((entry, i) => {
              const badge = statusBadge[entry.effectiveStatus] ?? statusBadge.failed;
              return (
                <tr key={i} className="border-b border-[#1f2937]/50 hover:bg-[#1f2937]/30 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-3.5 h-3.5 text-[#4b5563] flex-shrink-0" />
                      <div>
                        <div className="text-sm text-white font-medium">{entry.pipeline.name || extractRepoName(entry.pipeline.repo_url)}</div>
                        <div className="text-xs text-[#4b5563] truncate max-w-[200px]">{entry.pipeline.repo_url}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[#9ca3af] max-w-[180px] truncate">{entry.pipeline.goal}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                      style={{ color: badge.color, backgroundColor: badge.bg, border: `1px solid ${badge.color}33` }}>
                      {badge.icon}{badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-[#9ca3af] font-mono">{formatDuration(entry.duration_seconds)}</td>
                  <td className="px-4 py-3 text-sm text-[#4b5563]">{formatDate(entry.completedAt)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleView(entry)} className="p-1.5 hover:bg-[#374151] rounded-md transition-colors" title="View">
                        <Eye className="w-3.5 h-3.5 text-[#9ca3af]" />
                      </button>
                      {!entry.isRunning && (
                        <button onClick={(e) => { e.stopPropagation(); launchExecution(entry.pipeline); }}
                          className="p-1.5 hover:bg-accent/20 rounded-md transition-colors" title="Re-run">
                          <Play className="w-3.5 h-3.5 text-accent" />
                        </button>
                      )}
                      <button onClick={(e) => handleDelete(e, entry)} className="p-1.5 hover:bg-red-900/30 rounded-md transition-colors" title="Delete">
                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
