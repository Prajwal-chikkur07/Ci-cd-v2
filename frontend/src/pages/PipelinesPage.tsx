import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle, XCircle, Loader2, Clock, GitBranch,
  Play, Trash2, Eye, Plus, X, Rocket, Tag, Container,
} from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { deletePipeline } from '../api/client';
import { useParallelExecution } from '../hooks/useParallelExecution';
import { usePipeline } from '../hooks/usePipeline';
import type { HistoryEntry } from '../types/pipeline';

type Filter = 'all' | 'success' | 'failed' | 'running';

function extractRepoName(url: string) {
  try { return url.replace(/\.git$/, '').split('/').slice(-2).join('/'); }
  catch { return url; }
}

function formatDuration(s?: number | null) {
  if (!s) return '—';
  return s < 60 ? `${s.toFixed(0)}s` : `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
}

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
}

const statusBadge: Record<string, { label: string; color: string; bg: string; border: string; icon: React.ReactNode }> = {
  success:      { label: 'Success', color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', icon: <CheckCircle className="w-3 h-3" /> },
  failed:       { label: 'Failed',  color: '#dc2626', bg: '#fef2f2', border: '#fecaca', icon: <XCircle className="w-3 h-3" /> },
  partial:      { label: 'Partial', color: '#d97706', bg: '#fffbeb', border: '#fde68a', icon: <Clock className="w-3 h-3" /> },
  running:      { label: 'Running', color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe', icon: <Loader2 className="w-3 h-3 animate-spin" /> },
  not_executed: { label: 'Pending', color: '#6b7280', bg: '#f9fafb', border: '#e5e7eb', icon: <Clock className="w-3 h-3" /> },
};

const GOAL_SUGGESTIONS = [
  'build and test', 'lint, test, and build', 'run tests',
  'build and deploy', 'lint, test, build, and deploy', 'security scan and audit',
];

function NewPipelineModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { loading, error, generate, setError } = usePipeline();
  const { setPipeline, registerExecution, switchToExecution, currentPipeline, isExecuting } = usePipelineContext();
  const [repoUrl, setRepoUrl] = useState('');
  const [goal, setGoal] = useState('');
  const [name, setName] = useState('');
  const [useDocker, setUseDocker] = useState(false);
  const [showSugg, setShowSugg] = useState(false);
  const goalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (goalRef.current && !goalRef.current.contains(e.target as Node)) setShowSugg(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !goal.trim()) return;
    setError(null);
    const spec = await generate(repoUrl.trim(), goal.trim(), useDocker, name.trim());
    if (spec) {
      if (currentPipeline && isExecuting) {
        registerExecution(spec.pipeline_id, spec);
        switchToExecution(spec.pipeline_id);
      } else {
        setPipeline(spec);
      }
      onClose();
      navigate(`/pipeline/${spec.pipeline_id}`);
    }
  };

  const filtered = GOAL_SUGGESTIONS.filter(s => !goal.trim() || s.includes(goal.toLowerCase()));

  const inputCls = "w-full px-3.5 py-2.5 bg-white border border-[#e5e7eb] rounded-lg text-sm text-[#111827] placeholder-[#9ca3af] focus:ring-2 focus:ring-[#111827]/10 focus:border-[#111827] outline-none transition-all";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white border border-[#e5e7eb] rounded-2xl w-full max-w-md mx-4 shadow-xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f3f4f6]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#f3f4f6] flex items-center justify-center">
              <Rocket className="w-4 h-4 text-[#111827]" />
            </div>
            <h3 className="font-semibold text-[#111827]">New Pipeline</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-[#f3f4f6] rounded-lg transition-colors">
            <X className="w-4 h-4 text-[#6b7280]" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#374151] mb-1.5">Pipeline Name <span className="text-[#9ca3af] font-normal">(optional)</span></label>
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#9ca3af]" />
              <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. My App CI"
                className={`${inputCls} pl-9`} disabled={loading} />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#374151] mb-1.5">Repository URL</label>
            <div className="relative">
              <GitBranch className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#9ca3af]" />
              <input value={repoUrl} onChange={e => setRepoUrl(e.target.value)} placeholder="https://github.com/user/repo"
                className={`${inputCls} pl-9`} disabled={loading} />
            </div>
          </div>

          <div ref={goalRef} className="relative">
            <label className="block text-xs font-medium text-[#374151] mb-1.5">Deployment Goal</label>
            <input value={goal} onChange={e => setGoal(e.target.value)} onFocus={() => setShowSugg(true)}
              placeholder="e.g. build and test" className={inputCls} disabled={loading} />
            {showSugg && filtered.length > 0 && !loading && (
              <div className="absolute z-50 w-full mt-1 bg-white border border-[#e5e7eb] rounded-xl shadow-lg max-h-40 overflow-y-auto">
                {filtered.map(s => (
                  <button key={s} type="button" onClick={() => { setGoal(s); setShowSugg(false); }}
                    className="w-full text-left px-3.5 py-2.5 hover:bg-[#f9fafb] text-sm text-[#111827] transition-colors border-b border-[#f3f4f6] last:border-0">
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <label className="flex items-center gap-3 p-3 bg-[#f9fafb] rounded-lg cursor-pointer hover:bg-[#f3f4f6] border border-[#e5e7eb] transition-colors">
            <div className="relative">
              <input type="checkbox" checked={useDocker} onChange={e => setUseDocker(e.target.checked)} disabled={loading} className="sr-only peer" />
              <div className="w-9 h-5 bg-[#e5e7eb] rounded-full peer-checked:bg-[#111827] transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <Container className="w-4 h-4 text-[#6b7280]" />
            <span className="text-sm text-[#374151]">Run in Docker containers</span>
          </label>

          {error && <div className="p-3 bg-[#fef2f2] border border-[#fecaca] rounded-lg text-sm text-[#dc2626]">{error}</div>}

          {loading && (
            <div className="flex items-center gap-3 p-3 bg-[#f9fafb] border border-[#e5e7eb] rounded-lg">
              <Loader2 className="w-4 h-4 text-[#111827] animate-spin flex-shrink-0" />
              <span className="text-sm text-[#374151]">Analyzing repository...</span>
            </div>
          )}

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 bg-[#f3f4f6] hover:bg-[#e5e7eb] text-[#374151] text-sm font-medium rounded-lg transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={loading || !repoUrl.trim() || !goal.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#111827] hover:bg-[#1f2937] disabled:bg-[#e5e7eb] disabled:text-[#9ca3af] disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
              Generate
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PipelinesPage() {
  const { executionHistory, removeFromHistory, activeExecutions, loadFromHistory } = usePipelineContext();
  const { launchExecution } = useParallelExecution();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');
  const [showModal, setShowModal] = useState(false);

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
    <div className="flex-1 overflow-y-auto bg-[#f9fafb]">
      {showModal && <NewPipelineModal onClose={() => setShowModal(false)} />}

      {/* Header */}
      <div className="bg-white border-b border-[#e5e7eb] px-8 pt-7 pb-0">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Pipelines</h1>
            <p className="text-sm text-[#6b7280] mt-0.5">Manage and monitor all your CI/CD pipelines</p>
          </div>
          <button onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[#111827] hover:bg-[#1f2937] text-white text-sm font-medium rounded-lg transition-colors shadow-sm">
            <Plus className="w-4 h-4" />
            New Pipeline
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-0">
          {(['all', 'success', 'failed', 'running'] as Filter[]).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${
                filter === f
                  ? 'border-[#111827] text-[#111827]'
                  : 'border-transparent text-[#6b7280] hover:text-[#374151]'
              }`}>
              {f}
              <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
                filter === f ? 'bg-[#111827] text-white' : 'bg-[#f3f4f6] text-[#6b7280]'
              }`}>
                {counts[f]}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="px-8 py-6">
        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total Runs', value: counts.all,     color: '#111827' },
            { label: 'Successful', value: counts.success, color: '#16a34a' },
            { label: 'Failed',     value: counts.failed,  color: '#dc2626' },
            { label: 'Running',    value: counts.running, color: '#2563eb' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white border border-[#e5e7eb] rounded-xl p-4 shadow-card">
              <div className="text-xs text-[#6b7280] mb-1">{label}</div>
              <div className="text-2xl font-bold" style={{ color }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="bg-white border border-[#e5e7eb] rounded-xl shadow-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#f3f4f6]">
                {['Repository', 'Goal', 'Status', 'Duration', 'Date', 'Actions'].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-[#6b7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f3f4f6]">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16">
                    <div className="flex flex-col items-center gap-2 text-[#9ca3af]">
                      <GitBranch className="w-8 h-8" />
                      <p className="text-sm font-medium text-[#6b7280]">No pipelines found</p>
                      <button onClick={() => setShowModal(true)} className="text-xs text-[#111827] underline mt-1 hover:text-[#374151]">
                        Create your first pipeline
                      </button>
                    </div>
                  </td>
                </tr>
              ) : filtered.map((entry, i) => {
                const badge = statusBadge[entry.effectiveStatus] ?? statusBadge.failed;
                return (
                  <tr key={i} className="hover:bg-[#f9fafb] transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-[#f3f4f6] flex items-center justify-center flex-shrink-0">
                          <GitBranch className="w-3.5 h-3.5 text-[#6b7280]" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-[#111827]">{entry.pipeline.name || extractRepoName(entry.pipeline.repo_url)}</div>
                          <div className="text-xs text-[#9ca3af] truncate max-w-[180px]">{entry.pipeline.repo_url}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-[#6b7280] max-w-[160px] truncate">{entry.pipeline.goal}</td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                        style={{ color: badge.color, backgroundColor: badge.bg, borderColor: badge.border }}>
                        {badge.icon}{badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-[#6b7280] font-mono">{formatDuration(entry.duration_seconds)}</td>
                    <td className="px-5 py-3.5 text-sm text-[#9ca3af]">{formatDate(entry.completedAt)}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleView(entry)} className="p-1.5 hover:bg-[#f3f4f6] rounded-lg transition-colors" title="View">
                          <Eye className="w-3.5 h-3.5 text-[#6b7280]" />
                        </button>
                        {!entry.isRunning && (
                          <button onClick={e => { e.stopPropagation(); launchExecution(entry.pipeline); }}
                            className="p-1.5 hover:bg-[#f3f4f6] rounded-lg transition-colors" title="Re-run">
                            <Play className="w-3.5 h-3.5 text-[#6b7280]" />
                          </button>
                        )}
                        <button onClick={e => handleDelete(e, entry)} className="p-1.5 hover:bg-[#fef2f2] rounded-lg transition-colors" title="Delete">
                          <Trash2 className="w-3.5 h-3.5 text-[#ef4444]" />
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
    </div>
  );
}
