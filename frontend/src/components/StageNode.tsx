import { memo, useEffect, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import {
  Hammer, FlaskConical, Shield, Rocket, Activity,
  CheckCircle, XCircle, Clock, Loader2, SkipForward, ChevronDown,
} from 'lucide-react';
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
  pending: <Clock className="w-3.5 h-3.5" />,
  running: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  success: <CheckCircle className="w-3.5 h-3.5" />,
  failed:  <XCircle className="w-3.5 h-3.5" />,
  skipped: <SkipForward className="w-3.5 h-3.5" />,
};

interface StageNodeData {
  stage: Stage;
  status: StageStatus;
  onLogsClick?: () => void;
}

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

  const formatElapsed = (s: number) => s < 60 ? `${s.toFixed(0)}s` : `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;

  return (
    <div
      className={`rounded-xl border transition-all duration-300 w-[200px] ${status === 'running' ? 'animate-pulse-border' : ''}`}
      style={{ borderColor: config.border, backgroundColor: '#1a2332' }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#374151] !w-2 !h-2 !border-0" />

      <div className="px-3.5 py-3">
        {/* Status badge + title */}
        <div className="flex items-center gap-2 mb-2">
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1"
            style={{ color: config.text, backgroundColor: config.bg, border: `1px solid ${config.border}` }}
          >
            <span style={{ color: config.text }}>{statusIcons[status]}</span>
            {config.label}
          </span>
        </div>

        {/* Stage name */}
        <div className="font-semibold text-sm text-white mb-1 capitalize">
          {stage.id.replace(/_/g, ' ')}
        </div>

        {/* Agent */}
        <div className="flex items-center gap-1.5 mb-2">
          <span style={{ color: agentColor.color }}>{agentIcons[stage.agent]}</span>
          <span className="text-xs" style={{ color: agentColor.color }}>{agentColor.label}</span>
        </div>

        {/* Timer */}
        {status === 'running' && (
          <div className="text-xs font-mono text-[#10a37f]">{formatElapsed(elapsed)}</div>
        )}

        {/* Logs button */}
        <button className="mt-2 w-full flex items-center justify-center gap-1 text-[11px] text-[#4b5563] hover:text-[#9ca3af] transition-colors">
          <ChevronDown className="w-3 h-3" />
          Logs
        </button>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-[#374151] !w-2 !h-2 !border-0" />
    </div>
  );
}

export default memo(StageNodeComponent);
