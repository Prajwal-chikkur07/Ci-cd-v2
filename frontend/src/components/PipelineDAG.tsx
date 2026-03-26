import { useMemo, useCallback, useRef, useState, useEffect } from 'react';
import ReactFlow, {
  Background,
  MiniMap,
  Controls,
  type NodeTypes,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { usePipelineContext } from '../context/PipelineContext';
import { createNodesAndEdges } from '../utils/dagLayout';
import StageNode from './StageNode';

const nodeTypes: NodeTypes = {
  stageNode: StageNode,
};

export default function PipelineDAG() {
  const { currentPipeline, stageStatuses, selectStage } = usePipelineContext();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 0, height: 0 });

  // Measure the container and update on resize — ReactFlow needs real pixel dimensions
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const update = () => {
      setDims({ width: el.offsetWidth, height: el.offsetHeight });
    };
    update();

    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { nodes, edges } = useMemo(() => {
    if (!currentPipeline) return { nodes: [], edges: [] };
    return createNodesAndEdges(currentPipeline.stages, stageStatuses);
  }, [currentPipeline, stageStatuses]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      selectStage(node.id);
    },
    [selectStage],
  );

  if (!currentPipeline) return null;

  return (
    // Outer div fills the parent via flex-1; we measure it with ResizeObserver
    <div ref={containerRef} style={{ width: '100%', height: '100%', flex: 1 }}>
      {dims.height > 0 && (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          zoomOnScroll
          panOnScroll
          style={{ width: dims.width, height: dims.height }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e5e7eb" />
          <MiniMap
            nodeColor="#374151"
            maskColor="rgba(249,250,251,0.8)"
            className="!bg-white !border !border-[#e5e7eb] !rounded-lg"
          />
          <Controls className="!bg-white !border !border-[#e5e7eb] !rounded-lg !shadow-sm" />
        </ReactFlow>
      )}
    </div>
  );
}
