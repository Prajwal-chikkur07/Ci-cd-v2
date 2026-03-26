import { useState, useMemo } from 'react';
import { Search, Download, Copy, CheckCircle, XCircle, SkipForward, RotateCcw, Wrench, Info, Play, Flag, Terminal } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import type { LogType } from '../types/pipeline';

const levelConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  stage_success:    { color: '#16a34a', label: 'success', icon: <CheckCircle className="w-3 h-3" /> },
  recovery_success: { color: '#16a34a', label: 'success', icon: <CheckCircle className="w-3 h-3" /> },
  stage_failed:     { color: '#dc2626', label: 'error',   icon: <XCircle className="w-3 h-3" /> },
  recovery_failed:  { color: '#dc2626', label: 'error',   icon: <XCircle className="w-3 h-3" /> },
  stage_skipped:    { color: '#d97706', label: 'warning', icon: <SkipForward className="w-3 h-3" /> },
  retry:            { color: '#d97706', label: 'warning', icon: <RotateCcw className="w-3 h-3" /> },
  recovery_start:   { color: '#7c3aed', label: 'info',    icon: <Wrench className="w-3 h-3" /> },
  recovery_plan:    { color: '#7c3aed', label: 'info',    icon: <Wrench className="w-3 h-3" /> },
  stage_start:      { color: '#2563eb', label: 'info',    icon: <Play className="w-3 h-3" /> },
  pipeline_start:   { color: '#6b7280', label: 'info',    icon: <Flag className="w-3 h-3" /> },
  pipeline_done:    { color: '#6b7280', label: 'info',    icon: <Flag className="w-3 h-3" /> },
  stage_output:     { color: '#9ca3af', label: 'info',    icon: <Terminal className="w-3 h-3" /> },
  info:             { color: '#6b7280', label: 'info',    icon: <Info className="w-3 h-3" /> },
};

type LevelFilter = 'all' | 'info' | 'success' | 'warning' | 'error';

export default function LogsPage() {
  const { executionLogs } = usePipelineContext();
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('all');
  const [stageFilter, setStageFilter] = useState('all');
  const [copied, setCopied] = useState(false);

  const stages = useMemo(() => {
    const s = new Set<string>();
    executionLogs.forEach(l => { if (l.stage_id) s.add(l.stage_id); });
    return ['all', ...Array.from(s)];
  }, [executionLogs]);

  const filtered = useMemo(() => executionLogs.filter(log => {
    const cfg = levelConfig[log.type] ?? levelConfig.info;
    if (levelFilter !== 'all' && cfg.label !== levelFilter) return false;
    if (stageFilter !== 'all' && log.stage_id !== stageFilter) return false;
    if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }), [executionLogs, levelFilter, stageFilter, search]);

  const handleCopy = () => {
    const text = filtered.map(l => `[${new Date(l.timestamp).toLocaleTimeString()}] [${l.type}] ${l.stage_id ? `[${l.stage_id}] ` : ''}${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const text = filtered.map(l => `[${new Date(l.timestamp).toISOString()}] [${l.type}] ${l.stage_id ? `[${l.stage_id}] ` : ''}${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'pipeline-logs.txt'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex-1 overflow-hidden flex flex-col bg-[#f9fafb]">
      {/* Header */}
      <div className="bg-white border-b border-[#e5e7eb] px-8 pt-7 pb-5 flex-shrink-0">
        <h1 className="text-2xl font-bold text-[#111827]">Execution Logs</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">Search and filter real-time pipeline logs</p>
      </div>

      <div className="px-8 py-4 flex-shrink-0 flex items-center gap-3 flex-wrap bg-[#f9fafb]">
        {/* Search */}
        <div className="flex items-center gap-2 px-3.5 py-2 bg-white border border-[#e5e7eb] rounded-lg flex-1 min-w-[200px] shadow-card">
          <Search className="w-4 h-4 text-[#9ca3af]" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search logs..."
            className="bg-transparent text-sm text-[#111827] placeholder-[#9ca3af] outline-none flex-1" />
        </div>

        {/* Level filter */}
        <div className="flex gap-1 bg-white border border-[#e5e7eb] rounded-lg p-1 shadow-card">
          {(['all', 'info', 'success', 'warning', 'error'] as LevelFilter[]).map(l => (
            <button key={l} onClick={() => setLevelFilter(l)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors capitalize ${
                levelFilter === l ? 'bg-[#111827] text-white' : 'text-[#6b7280] hover:text-[#111827]'
              }`}>
              {l}
            </button>
          ))}
        </div>

        {/* Stage filter */}
        <select value={stageFilter} onChange={e => setStageFilter(e.target.value)}
          className="px-3 py-2 bg-white border border-[#e5e7eb] rounded-lg text-sm text-[#374151] outline-none shadow-card">
          {stages.map(s => <option key={s} value={s}>{s === 'all' ? 'All Stages' : s}</option>)}
        </select>

        <button onClick={handleCopy} className="flex items-center gap-1.5 px-3 py-2 bg-white border border-[#e5e7eb] rounded-lg text-sm text-[#6b7280] hover:text-[#111827] transition-colors shadow-card">
          <Copy className="w-3.5 h-3.5" />{copied ? 'Copied!' : 'Copy'}
        </button>
        <button onClick={handleDownload} className="flex items-center gap-1.5 px-3 py-2 bg-white border border-[#e5e7eb] rounded-lg text-sm text-[#6b7280] hover:text-[#111827] transition-colors shadow-card">
          <Download className="w-3.5 h-3.5" />Download
        </button>
        <span className="text-xs text-[#9ca3af]">{filtered.length} entries</span>
      </div>

      {/* Terminal */}
      <div className="flex-1 mx-8 mb-6 bg-[#111827] border border-[#e5e7eb] rounded-xl overflow-y-auto font-mono text-xs shadow-card">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[#6b7280]">
            <Terminal className="w-8 h-8 mb-2 text-[#374151]" />
            <p className="text-[#9ca3af]">{executionLogs.length === 0 ? 'No logs yet. Execute a pipeline to see logs.' : 'No logs match your filters.'}</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-[#1f2937] border-b border-[#374151]">
              <tr>
                {['Timestamp', 'Level', 'Stage', 'Message'].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-[10px] font-semibold text-[#6b7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((log, i) => {
                const cfg = levelConfig[log.type] ?? levelConfig.info;
                return (
                  <tr key={i} className="border-b border-[#1f2937] hover:bg-[#1f2937]/50">
                    <td className="px-4 py-1.5 text-[#6b7280] whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="px-4 py-1.5">
                      <span className="flex items-center gap-1" style={{ color: cfg.color }}>
                        {cfg.icon}
                        <span className="uppercase text-[10px] font-bold">{cfg.label}</span>
                      </span>
                    </td>
                    <td className="px-4 py-1.5 text-[#6b7280]">{log.stage_id ?? '—'}</td>
                    <td className="px-4 py-1.5 text-[#d1d5db] max-w-[500px] truncate">{log.message}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
