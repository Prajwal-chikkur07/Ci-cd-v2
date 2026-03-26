import { memo, useEffect, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Hammer, FlaskConical, Shield, Rocket, Activity, CheckCircle, XCircle, Clock, Loader2, SkipForward, ChevronDown } from 'lucide-react';
import type { Stage, StageStatus, AgentType } from '../types/pipeline';
import { statusConfig, agentColors } from '../utils/statusColors';

const agentIcons: Record<AgentType, React.ReactNode> = {
  build:    <Hammer className="w-3.5 h-3.5" />,
  test:     <FlaskConical className="w-3.5 h-3.5" />,
  security: <Shield className="w-3.5 h-3.5" />,
  deploy:   <Rocket className="w-3.5 h-3.5" />,
  verify:   <Activity className="w-3.5 h-3.5" />,
};

const statusIcons: Record<StageStatus, React.ReactNode> = {
  pending: <Clock className="w-3 h-3" />,
  running: <Loader2 className="w-3 h-3 animate-spin" />,
  success: <CheckCircle className="w-3 h-3" />,
  failed:  <XCircle className="w-3 h-3" />,
  skipped: <SkipForward className="w-3 h-3" />,
};

interface StageNodeData { stage: Stage; status: StageStatus; }

function StageNodeComponent({ data }: NodeProps<StageNodeData>) {
  const { stage, status } = data;
  const config = statusConfig[status];
  const agentColor = agentColors[stage.agent];
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== 'running') { setElapsed(0); return; }
    const start = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - start) / 1000), 100);
    return () => clearInterval(timer);
  }, [status]);

  return (
    <div
      className={`rounded-xl border bg-white shadow-card transition-all duration-200 w-[200px] hover:shadow-card-hover ${status === 'running' ? 'animate-pulse-border' : ''}`}
      style={{ borderColor: config.border }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#e5e7eb] !w-2 !h-2 !border-0" />
      <div className="px-3.5 py-3">
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 border"
            style={{ color: config.text, backgroundColor: config.bg, borderColor: config.border }}>
            <span>{statusIcons[status]}</span>
            {config.label}
          </span>
        </div>
        <div className="font-semibold text-sm text-[#111827] mb-1 capitalize">{stage.id.replace(/_/g, ' ')}</div>
        <div className="flex items-center gap-1.5 mb-1">
          <span style={{ color: agentColor.color }}>{agentIcons[stage.agent]}</span>
          <span className="text-xs text-[#6b7280]">{agentColor.label}</span>
        </div>
        {status === 'running' && (
          <div className="text-xs font-mono text-[#111827] mt-1">{elapsed.toFixed(0)}s</div>
        )}
        <button className="mt-2 w-full flex items-center justify-center gap-1 text-[11px] text-[#9ca3af] hover:text-[#6b7280] transition-colors">
          <ChevronDown className="w-3 h-3" />Logs
        </button>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-[#e5e7eb] !w-2 !h-2 !border-0" />
    </div>
  );
}

export default memo(StageNodeComponent);
