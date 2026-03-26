import { useEffect, useRef, useState } from 'react';
import {
  Play, CheckCircle, XCircle, SkipForward, RotateCcw,
  Wrench, Zap, Info, Flag, ChevronDown, ChevronUp,
  ScrollText, Terminal,
} from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import type { LogEntry, LogType } from '../types/pipeline';

const logConfig: Record<LogType, { icon: typeof Play; color: string; label: string }> = {
  pipeline_start:   { icon: Flag,         color: '#6366f1', label: 'Pipeline' },
  pipeline_done:    { icon: Flag,         color: '#6366f1', label: 'Pipeline' },
  stage_start:      { icon: Play,         color: '#60a5fa', label: 'Start' },
  stage_success:    { icon: CheckCircle,  color: '#10a37f', label: 'Success' },
  stage_failed:     { icon: XCircle,      color: '#ef4444', label: 'Failed' },
  stage_skipped:    { icon: SkipForward,  color: '#f59e0b', label: 'Skipped' },
  stage_output:     { icon: Terminal,     color: '#6b7280', label: 'stdout' },
  retry:            { icon: RotateCcw,    color: '#f59e0b', label: 'Retry' },
  recovery_start:   { icon: Wrench,       color: '#a78bfa', label: 'Healing' },
  recovery_plan:    { icon: Zap,          color: '#a78bfa', label: 'Plan' },
  recovery_success: { icon: CheckCircle,  color: '#10a37f', label: 'Healed' },
  recovery_failed:  { icon: XCircle,      color: '#ef4444', label: 'Heal Fail' },
  info:             { icon: Info,         color: '#6b7280', label: 'Info' },
};

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ''; }
}

function StdoutBlock({ stageId, lines }: { stageId: string; lines: string[] }) {
  const [open, setOpen] = useState(true);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (open && preRef.current) preRef.current.scrollTop = preRef.current.scrollHeight;
  }, [lines.length, open]);

  if (lines.length === 0) return null;

  return (
    <div className="ml-7 mb-1">
      <button onClick={() => setOpen(v => !v)} className="flex items-center gap-1 text-[10px] text-[#9ca3af] hover:text-[#6b7280] mb-0.5">
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <Terminal className="w-3 h-3" />
        <span>{stageId} stdout ({lines.length} lines)</span>
      </button>
      {open && (
        <pre ref={preRef} className="bg-[#111827] text-[#22c55e] text-[10px] font-mono p-2 rounded overflow-y-auto max-h-40 whitespace-pre-wrap border border-[#e5e7eb]">
          {lines.join('\n')}
        </pre>
      )}
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const config = logConfig[entry.type] || logConfig.info;
  const Icon = config.icon;
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex items-start gap-2 px-3 py-2 hover:bg-[#f9fafb] transition-colors group"
      onClick={() => entry.details && setExpanded(!expanded)}
      style={{ cursor: entry.details ? 'pointer' : 'default' }}>
      <div className="flex flex-col items-center flex-shrink-0 pt-0.5">
        <div className="w-5 h-5 rounded-full flex items-center justify-center bg-[#f3f4f6]">
          <Icon className="w-3 h-3" style={{ color: config.color }} />
        </div>
        <div className="w-px flex-1 bg-[#f3f4f6] mt-1" />
      </div>
      <div className="flex-1 min-w-0 pb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#f3f4f6]" style={{ color: config.color }}>
            {config.label}
          </span>
          {entry.stage_id && <span className="text-[10px] font-mono text-[#9ca3af] truncate">{entry.stage_id}</span>}
          <span className="text-[10px] text-[#d1d5db] ml-auto flex-shrink-0">{formatTime(entry.timestamp)}</span>
          {entry.details && (expanded ? <ChevronUp className="w-2.5 h-2.5 text-[#9ca3af]" /> : <ChevronDown className="w-2.5 h-2.5 text-[#9ca3af] opacity-0 group-hover:opacity-100" />)}
        </div>
        <p className="text-[11px] text-[#6b7280] mt-0.5 leading-relaxed">{entry.message}</p>
        {expanded && entry.details && (
          <pre className="text-[10px] font-mono bg-[#111827] text-[#d1d5db] p-2 rounded mt-1.5 overflow-x-auto whitespace-pre-wrap max-h-28 overflow-y-auto border border-[#e5e7eb]">
            {entry.details}
          </pre>
        )}
      </div>
    </div>
  );
}

export default function ExecutionLog() {
  const { executionLogs, isExecuting } = usePipelineContext();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [executionLogs.length]);

  const stdoutByStage: Record<string, string[]> = {};
  const insertedStdout = new Set<string>();
  const rendered: Array<{ type: 'event'; entry: LogEntry; idx: number } | { type: 'stdout'; stageId: string; lines: string[] }> = [];

  for (const entry of executionLogs) {
    if (entry.type === 'stage_output' && entry.stage_id) {
      if (!stdoutByStage[entry.stage_id]) stdoutByStage[entry.stage_id] = [];
      stdoutByStage[entry.stage_id].push(entry.message);
    }
  }

  for (let i = 0; i < executionLogs.length; i++) {
    const entry = executionLogs[i];
    if (entry.type === 'stage_output') continue;
    rendered.push({ type: 'event', entry, idx: i });
    if (entry.type === 'stage_start' && entry.stage_id && !insertedStdout.has(entry.stage_id)) {
      insertedStdout.add(entry.stage_id);
      rendered.push({ type: 'stdout', stageId: entry.stage_id, lines: stdoutByStage[entry.stage_id] ?? [] });
    }
  }

  const eventCount = executionLogs.filter(l => l.type !== 'stage_output').length;

  return (
    <aside className="w-[280px] bg-white border-l border-[#e5e7eb] flex flex-col flex-shrink-0 h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#f3f4f6] flex-shrink-0">
        <ScrollText className="w-4 h-4 text-[#6b7280]" />
        <h3 className="text-xs font-semibold text-[#374151] uppercase tracking-wider">Execution Log</h3>
        <span className="text-[10px] text-[#9ca3af]">{eventCount} events</span>
        {isExecuting && <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse ml-auto" />}
      </div>

      <div className="flex-1 overflow-y-auto">
        {rendered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[#9ca3af] px-4">
            <ScrollText className="w-7 h-7 mb-2 text-[#e5e7eb]" />
            <p className="text-xs text-center">No logs yet. Execute a pipeline to see real-time logs here.</p>
          </div>
        ) : (
          rendered.map((item, i) =>
            item.type === 'event'
              ? <LogLine key={item.idx} entry={item.entry} />
              : <StdoutBlock key={`stdout-${item.stageId}`} stageId={item.stageId} lines={item.lines} />
          )
        )}
        <div ref={bottomRef} />
      </div>

      {!isExecuting && executionLogs.length > 0 && (
        <div className="px-4 py-2 border-t border-[#f3f4f6] flex-shrink-0">
          <div className="flex items-center gap-3 text-[10px] text-[#9ca3af]">
            <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-[#22c55e]" />{executionLogs.filter(l => l.type === 'stage_success').length}</span>
            <span className="flex items-center gap-1"><XCircle className="w-3 h-3 text-[#ef4444]" />{executionLogs.filter(l => l.type === 'stage_failed').length}</span>
            <span className="flex items-center gap-1"><SkipForward className="w-3 h-3 text-[#f59e0b]" />{executionLogs.filter(l => l.type === 'stage_skipped').length}</span>
            <span className="flex items-center gap-1"><RotateCcw className="w-3 h-3 text-[#f59e0b]" />{executionLogs.filter(l => l.type === 'retry').length}</span>
            <span className="flex items-center gap-1"><Wrench className="w-3 h-3 text-[#8b5cf6]" />{executionLogs.filter(l => l.type === 'recovery_start').length}</span>
          </div>
        </div>
      )}
    </aside>
  );
}
