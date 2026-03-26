import { useEffect, useRef, useState } from 'react';
import {
  Play, CheckCircle, XCircle, SkipForward, RotateCcw,
  Wrench, Zap, Info, Flag, ChevronDown, ChevronUp,
  ScrollText, Terminal,
} from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import type { LogEntry, LogType } from '../types/pipeline';

const logConfig: Record<LogType, { icon: typeof Play; color: string; bg: string; label: string }> = {
  pipeline_start:   { icon: Flag,         color: '#6366f1', bg: '#eef2ff', label: 'Pipeline' },
  pipeline_done:    { icon: Flag,         color: '#6366f1', bg: '#eef2ff', label: 'Pipeline' },
  stage_start:      { icon: Play,         color: '#3b82f6', bg: '#eff6ff', label: 'Start' },
  stage_success:    { icon: CheckCircle,  color: '#059669', bg: '#ecfdf5', label: 'Success' },
  stage_failed:     { icon: XCircle,      color: '#dc2626', bg: '#fef2f2', label: 'Failed' },
  stage_skipped:    { icon: SkipForward,  color: '#ca8a04', bg: '#fefce8', label: 'Skipped' },
  stage_output:     { icon: Terminal,     color: '#6b7280', bg: '#f3f4f6', label: 'stdout' },
  retry:            { icon: RotateCcw,    color: '#f59e0b', bg: '#fffbeb', label: 'Retry' },
  recovery_start:   { icon: Wrench,       color: '#8b5cf6', bg: '#f5f3ff', label: 'Healing' },
  recovery_plan:    { icon: Zap,          color: '#8b5cf6', bg: '#f5f3ff', label: 'Plan' },
  recovery_success: { icon: CheckCircle,  color: '#059669', bg: '#ecfdf5', label: 'Healed' },
  recovery_failed:  { icon: XCircle,      color: '#dc2626', bg: '#fef2f2', label: 'Heal Fail' },
  info:             { icon: Info,         color: '#6b7280', bg: '#f9fafb', label: 'Info' },
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ''; }
}

/** Collapsible stdout block shown inline after stage_start */
function StdoutBlock({ stageId, lines }: { stageId: string; lines: string[] }) {
  const [open, setOpen] = useState(true);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (open && preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [lines.length, open]);

  if (lines.length === 0) return null;

  return (
    <div className="ml-7 mb-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-600 mb-0.5"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <Terminal className="w-3 h-3" />
        <span>{stageId} stdout ({lines.length} lines)</span>
      </button>
      {open && (
        <pre
          ref={preRef}
          className="bg-gray-900 text-emerald-300 text-[10px] font-mono p-2 rounded overflow-y-auto max-h-40 whitespace-pre-wrap"
        >
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
    <div
      className="flex items-start gap-2 px-3 py-2 hover:bg-gray-50/50 transition-colors group"
      onClick={() => entry.details && setExpanded(!expanded)}
      style={{ cursor: entry.details ? 'pointer' : 'default' }}
    >
      <div className="flex flex-col items-center flex-shrink-0 pt-0.5">
        <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ backgroundColor: config.bg }}>
          <Icon className="w-3 h-3" style={{ color: config.color }} />
        </div>
        <div className="w-px flex-1 bg-gray-100 mt-1" />
      </div>
      <div className="flex-1 min-w-0 pb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded" style={{ backgroundColor: config.bg, color: config.color }}>
            {config.label}
          </span>
          {entry.stage_id && (
            <span className="text-[10px] font-mono text-gray-400 truncate">{entry.stage_id}</span>
          )}
          <span className="text-[10px] text-gray-300 ml-auto flex-shrink-0">{formatTime(entry.timestamp)}</span>
          {entry.details && (
            expanded
              ? <ChevronUp className="w-2.5 h-2.5 text-gray-300" />
              : <ChevronDown className="w-2.5 h-2.5 text-gray-300 opacity-0 group-hover:opacity-100" />
          )}
        </div>
        <p className="text-[11px] text-gray-600 mt-0.5 leading-relaxed">{entry.message}</p>
        {expanded && entry.details && (
          <pre className="text-[10px] font-mono bg-gray-900 text-gray-300 p-2 rounded mt-1.5 overflow-x-auto whitespace-pre-wrap max-h-28 overflow-y-auto">
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
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [executionLogs.length]);

  // Build a merged render list: non-output events + grouped stdout blocks per stage
  // We insert a stdout block right after each stage_start event
  const rendered: Array<{ type: 'event'; entry: LogEntry; idx: number } | { type: 'stdout'; stageId: string; lines: string[] }> = [];
  const stdoutByStage: Record<string, string[]> = {};
  const insertedStdout = new Set<string>();

  // Pre-collect stdout lines per stage
  for (const entry of executionLogs) {
    if (entry.type === 'stage_output' && entry.stage_id) {
      if (!stdoutByStage[entry.stage_id]) stdoutByStage[entry.stage_id] = [];
      stdoutByStage[entry.stage_id].push(entry.message);
    }
  }

  for (let i = 0; i < executionLogs.length; i++) {
    const entry = executionLogs[i];
    if (entry.type === 'stage_output') continue; // handled via StdoutBlock

    rendered.push({ type: 'event', entry, idx: i });

    // After stage_start, insert the live stdout block for that stage
    if (entry.type === 'stage_start' && entry.stage_id && !insertedStdout.has(entry.stage_id)) {
      insertedStdout.add(entry.stage_id);
      rendered.push({ type: 'stdout', stageId: entry.stage_id, lines: stdoutByStage[entry.stage_id] ?? [] });
    }
  }

  const eventCount = executionLogs.filter((l) => l.type !== 'stage_output').length;

  return (
    <aside className="w-[300px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0 h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 flex-shrink-0">
        <ScrollText className="w-4 h-4 text-gray-500" />
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Execution Log</h3>
        <span className="text-[10px] text-gray-400 font-normal normal-case">{eventCount} events</span>
        {isExecuting && <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse ml-auto" />}
      </div>

      <div className="flex-1 overflow-y-auto">
        {rendered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 px-4">
            <ScrollText className="w-8 h-8 mb-2 text-gray-300" />
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
        <div className="px-4 py-2 border-t border-gray-100 flex-shrink-0">
          <div className="flex items-center gap-3 text-[10px] text-gray-400">
            <span className="flex items-center gap-1">
              <CheckCircle className="w-3 h-3 text-emerald-400" />
              {executionLogs.filter((l) => l.type === 'stage_success' || l.type === 'recovery_success').length}
            </span>
            <span className="flex items-center gap-1">
              <XCircle className="w-3 h-3 text-red-400" />
              {executionLogs.filter((l) => l.type === 'stage_failed' || l.type === 'recovery_failed').length}
            </span>
            <span className="flex items-center gap-1">
              <SkipForward className="w-3 h-3 text-amber-400" />
              {executionLogs.filter((l) => l.type === 'stage_skipped').length}
            </span>
            <span className="flex items-center gap-1">
              <RotateCcw className="w-3 h-3 text-orange-400" />
              {executionLogs.filter((l) => l.type === 'retry').length}
            </span>
            <span className="flex items-center gap-1">
              <Wrench className="w-3 h-3 text-purple-400" />
              {executionLogs.filter((l) => l.type === 'recovery_start').length}
            </span>
          </div>
        </div>
      )}
    </aside>
  );
}
