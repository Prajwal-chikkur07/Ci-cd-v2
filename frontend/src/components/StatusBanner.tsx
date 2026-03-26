import { Wrench, ExternalLink } from 'lucide-react';
import { usePipelineContext } from '../context/PipelineContext';

export default function StatusBanner() {
  const { recoveryPlans, deployUrl } = usePipelineContext();

  return (
    <>
      {deployUrl && (
        <div className="mx-5 mt-3 px-4 py-3 rounded-lg flex items-center gap-3 text-sm font-medium bg-[#f0fdf4] border border-[#bbf7d0] text-[#16a34a]">
          <ExternalLink className="w-4 h-4 flex-shrink-0" />
          <span>Deployment live at{' '}
            <a href={deployUrl} target="_blank" rel="noopener noreferrer" className="underline font-semibold hover:text-[#15803d]">{deployUrl}</a>
          </span>
        </div>
      )}
      {recoveryPlans.size > 0 && (() => {
        const [stageId, plan] = Array.from(recoveryPlans.entries()).slice(-1)[0];
        return (
          <div className="mx-5 mt-3 px-4 py-3 rounded-lg flex items-center gap-3 text-sm font-medium bg-[#fffbeb] border border-[#fde68a] text-[#d97706]">
            <Wrench className="w-4 h-4 flex-shrink-0" />
            <span>Recovery for <span className="font-semibold font-mono">{stageId}</span>: <span className="font-semibold">{plan.strategy.replace(/_/g, ' ')}</span>
              {plan.reason && <span className="font-normal"> — {plan.reason}</span>}
            </span>
          </div>
        );
      })()}
    </>
  );
}
