const dagre = require('dagre');

// Simulate the stages from nodejs template
const stages = [
  { id: 'install', depends_on: [] },
  { id: 'lint', depends_on: ['install'] },
  { id: 'unit_test', depends_on: ['install'] },
  { id: 'build', depends_on: ['lint', 'unit_test'] },
];

const g = new dagre.graphlib.Graph();
g.setDefaultEdgeLabel(() => ({}));
g.setGraph({ rankdir: 'TB', ranksep: 80, nodesep: 60 });

for (const stage of stages) {
  g.setNode(stage.id, { width: 200, height: 80 });
}

for (const stage of stages) {
  for (const dep of stage.depends_on) {
    g.setEdge(dep, stage.id);
  }
}

dagre.layout(g);

console.log('Node positions:');
for (const stage of stages) {
  const pos = g.node(stage.id);
  console.log(`${stage.id}: x=${pos.x}, y=${pos.y}`);
}

console.log('\nEdges:');
for (const stage of stages) {
  for (const dep of stage.depends_on) {
    console.log(`${dep} -> ${stage.id}`);
  }
}
