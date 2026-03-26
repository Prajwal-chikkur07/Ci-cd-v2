import { useMemo, useCallback } from 'react';
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
    <div className="flex-1 min-h-[400px] w-full">
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
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1f2937" />
        <MiniMap
          nodeColor="#374151"
          maskColor="rgba(15,23,42,0.8)"
          className="!bg-[#111827] !border !border-[#1f2937] !rounded-lg"
        />
        <Controls className="!bg-[#111827] !border !border-[#1f2937] !rounded-lg" />
      </ReactFlow>
    </div>
  );
}
