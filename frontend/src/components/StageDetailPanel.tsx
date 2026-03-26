import { useState, useRef, useEffect } from 'react';
import { X, Terminal, Info, Clock, RotateCcw, AlertTriangle, Zap, ScrollText, ExternalLink } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';
import { statusConfig, agentColors } from '../utils/statusColors';
import type { LogType } from '../types/pipeline';

const recoveryBadgeConfig: Record<string, { bg: string; text: string; border: string }> = {
  FIX_AND_RETRY: { bg: '#064e3b33', text: '#10a37f', border: '#10a37f44' },
  SKIP_STAGE:    { bg: '#78350f22', text: '#f59e0b', border: '#f59e0b44' },
  ROLLBACK:      { bg: '#7c2d1222', text: '#fb923c', border: '#fb923c44' },
  ABORT:         { bg: '#7f1d1d22', text: '#ef4444', border: '#ef444444' },
};

const logTypeColors: Record<string, { color: string; label: string }> = {
  stage_start:      { color: '#60a5fa', label: 'START' },
  stage_success:    { color: '#10a37f', label: 'SUCCESS' },
  stage_failed:     { color: '#ef4444', label: 'FAILED' },
  stage_skipped:    { color: '#f59e0b', label: 'SKIPPED' },
  retry:            { color: '#f59e0b', label: 'RETRY' },
  recovery_start:   { color: '#a78bfa', label: 'HEALING' },
  recovery_plan:    { color: '#a78bfa', label: 'PLAN' },
  recovery_success: { color: '#10a37f', label: 'HEALED' },
  recovery_failed:  { color: '#ef4444', label: 'HEAL FAIL' },
  info:             { color: '#6b7280', label: 'INFO' },
};

export default function StageDetailPanel() {
  const { currentPipeline, selectedStageId, stageStatuses, stageResults, recoveryPlans, executionLogs, selectStage, deployUrl } =
    usePipelineContext();
  const [tab, setTab] = useState<'output' | 'details' | 'logs'>('output');
  const liveOutputRef = useRef<HTMLPreElement>(null);

  const liveLineCount = executionLogs.filter(l => l.stage_id === selectedStageId && l.type === 'stage_output').length;
  useEffect(() => {
    if (liveOutputRef.current) liveOutputRef.current.scrollTop = liveOutputRef.current.scrollHeight;
  }, [liveLineCount]);

  if (!selectedStageId || !currentPipeline) return null;

  const stage = currentPipeline.stages.find(s => s.id === selectedStageId);
  if (!stage) return null;

  const status = stageStatuses.get(stage.id) ?? 'pending';
  const result = stageResults.get(stage.id);
  const config = statusConfig[status];
  const agentColor = agentColors[stage.agent];
  const recovery = recoveryPlans.get(stage.id);

  const tabClass = (t: string) => `flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors ${
    tab === t ? 'border-accent text-accent' : 'border-transparent text-[#4b5563] hover:text-[#9ca3af]'
  }`;

  return (
    <div className="fixed top-0 right-0 h-full w-[420px] bg-[#111827] border-l border-[#1f2937] shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[#1f2937] flex items-center justify-between flex-shrink-0">
        <div>
          <h3 className="font-semibold text-white capitalize">{stage.id.replace(/_/g, ' ')}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ backgroundColor: agentColor.color + '15', color: agentColor.color }}>
              {agentColor.label}
            </span>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ backgroundColor: config.bg, color: config.text, border: `1px solid ${config.border}` }}>
              {config.label}
            </span>
            {result && (
              <span className="text-xs text-[#4b5563] flex items-center gap-1">
                <Clock className="w-3 h-3" />{result.duration_seconds.toFixed(1)}s
              </span>
            )}
          </div>
        </div>
        <button onClick={() => selectStage(null)} className="p-1.5 hover:bg-[#1f2937] rounded-lg transition-colors">
          <X className="w-5 h-5 text-[#4b5563]" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#1f2937] px-5 flex-shrink-0">
        <button onClick={() => setTab('output')} className={tabClass('output')}><Terminal className="w-3.5 h-3.5" />Output</button>
        <button onClick={() => setTab('details')} className={tabClass('details')}><Info className="w-3.5 h-3.5" />Details</button>
        <button onClick={() => setTab('logs')} className={tabClass('logs')}><ScrollText className="w-3.5 h-3.5" />Logs</button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        {tab === 'logs' ? (
          <div className="space-y-1">
            {(() => {
              const stageLogs = executionLogs.filter(l => l.stage_id === stage.id);
              if (stageLogs.length === 0) return <div className="text-sm text-[#374151] text-center py-8">No log entries for this stage yet</div>;
              return stageLogs.map((entry, i) => {
                const cfg = logTypeColors[entry.type] || logTypeColors.info;
                return (
                  <div key={i} className="flex items-start gap-2 py-1.5">
                    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5 bg-[#1f2937]" style={{ color: cfg.color }}>{cfg.label}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[#9ca3af] leading-relaxed">{entry.message}</p>
                      {entry.details && <pre className="text-[10px] font-mono bg-[#020617] text-[#9ca3af] p-2 rounded mt-1 overflow-x-auto whitespace-pre-wrap max-h-24 overflow-y-auto border border-[#1f2937]">{entry.details}</pre>}
                    </div>
                    <span className="text-[10px] text-[#374151] flex-shrink-0 mt-0.5">{new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                  </div>
                );
              });
            })()}
          </div>
        ) : tab === 'output' ? (
          <div className="space-y-3">
            {status === 'running' && (() => {
              const liveLines = executionLogs.filter(l => l.stage_id === stage.id && l.type === 'stage_output').map(l => l.message);
              if (liveLines.length > 0) return (
                <div>
                  <label className="text-xs font-medium text-accent uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse inline-block" />Live Output
                  </label>
                  <pre ref={liveOutputRef} className="bg-[#020617] text-[#10a37f] text-xs font-mono p-4 rounded-lg overflow-x-auto whitespace-pre-wrap max-h-[400px] overflow-y-auto border border-[#1f2937]">{liveLines.join('\n')}</pre>
                </div>
              );
              return <div className="text-sm text-[#374151] text-center py-8 flex flex-col items-center gap-2"><span className="w-2 h-2 rounded-full bg-accent animate-pulse" />Waiting for output...</div>;
            })()}

            {status !== 'running' && result?.stdout ? (
              <div>
                <label className="text-xs font-medium text-[#4b5563] uppercase tracking-wider mb-1.5 block">stdout</label>
                <pre className="bg-[#020617] text-[#10a37f] text-xs font-mono p-4 rounded-lg overflow-x-auto whitespace-pre-wrap max-h-[400px] overflow-y-auto border border-[#1f2937]">{result.stdout}</pre>
              </div>
            ) : status !== 'running' && (
              <div className="text-sm text-[#374151] text-center py-8">{status === 'pending' ? 'Stage has not run yet' : 'No output captured'}</div>
            )}

            {result?.stderr && (
              <div>
                <label className="text-xs font-medium text-red-400 uppercase tracking-wider mb-1.5 block">stderr</label>
                <pre className="bg-[#1a0a0a] text-red-400 text-xs font-mono p-4 rounded-lg overflow-x-auto whitespace-pre-wrap max-h-[300px] overflow-y-auto border border-red-900/30">{result.stderr}</pre>
              </div>
            )}

            {stage.agent === 'deploy' && deployUrl && status === 'success' && (
              <a href={deployUrl} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium bg-accent/10 text-accent border border-accent/20">
                <ExternalLink className="w-4 h-4" />Application running at {deployUrl}
              </a>
            )}

            {result && result.exit_code !== 0 && result.exit_code !== -1 && (
              <div className="flex items-center gap-2 text-sm text-red-400 bg-red-900/20 px-3 py-2 rounded-lg border border-red-800/30">
                <AlertTriangle className="w-4 h-4" />Exit code: {result.exit_code}
              </div>
            )}

            {recovery && (
              <div className="border border-[#1f2937] rounded-lg overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2 bg-[#1f2937] border-b border-[#374151]">
                  <Zap className="w-3.5 h-3.5 text-[#4b5563]" />
                  <span className="text-xs font-medium text-[#9ca3af] uppercase tracking-wider">Recovery Plan</span>
                </div>
                <div className="p-3 space-y-2">
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full inline-block"
                    style={{ backgroundColor: (recoveryBadgeConfig[recovery.strategy] ?? recoveryBadgeConfig.ABORT).bg, color: (recoveryBadgeConfig[recovery.strategy] ?? recoveryBadgeConfig.ABORT).text, border: `1px solid ${(recoveryBadgeConfig[recovery.strategy] ?? recoveryBadgeConfig.ABORT).border}` }}>
                    {recovery.strategy.replace(/_/g, ' ')}
                  </span>
                  <p className="text-sm text-[#9ca3af]">{recovery.reason}</p>
                  {recovery.modified_command && (
                    <div>
                      <label className="text-xs font-medium text-[#4b5563] uppercase tracking-wider mb-1 block">Modified Command</label>
                      <pre className="bg-[#020617] text-yellow-400 text-xs font-mono p-3 rounded-lg overflow-x-auto whitespace-pre-wrap border border-[#1f2937]">{recovery.modified_command}</pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-[#4b5563] uppercase tracking-wider mb-1.5 block">Command</label>
              <pre className="bg-[#1f2937] text-[#e2e8f0] text-sm font-mono p-3 rounded-lg border border-[#374151] whitespace-pre-wrap">{stage.command}</pre>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Timeout', value: `${stage.timeout_seconds}s` },
                { label: 'Retries', value: stage.retry_count, icon: <RotateCcw className="w-3 h-3 inline mr-1" /> },
                { label: 'Critical', value: stage.critical ? 'Yes' : 'No' },
                { label: 'Agent', value: agentColor.label, color: agentColor.color },
              ].map(({ label, value, icon, color }) => (
                <div key={label} className="bg-[#1f2937] rounded-lg p-3 border border-[#374151]">
                  <div className="text-xs text-[#4b5563]">{label}</div>
                  <div className="text-sm font-medium mt-0.5" style={color ? { color } : { color: '#e2e8f0' }}>{icon}{value}</div>
                </div>
              ))}
            </div>
            {stage.depends_on.length > 0 && (
              <div>
                <label className="text-xs font-medium text-[#4b5563] uppercase tracking-wider mb-1.5 block">Depends On</label>
                <div className="flex flex-wrap gap-1.5">
                  {stage.depends_on.map(dep => <span key={dep} className="text-xs bg-[#1f2937] text-[#9ca3af] px-2 py-1 rounded-md font-mono border border-[#374151]">{dep}</span>)}
                </div>
              </div>
            )}
            {Object.keys(stage.env_vars).length > 0 && (
              <div>
                <label className="text-xs font-medium text-[#4b5563] uppercase tracking-wider mb-1.5 block">Environment Variables</label>
                <div className="bg-[#1f2937] rounded-lg p-3 space-y-1 border border-[#374151]">
                  {Object.entries(stage.env_vars).map(([k, v]) => (
                    <div key={k} className="text-xs font-mono">
                      <span className="text-[#60a5fa]">{k}</span>
                      <span className="text-[#374151]">=</span>
                      <span className="text-[#9ca3af]">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
