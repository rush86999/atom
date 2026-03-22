import GraphVisualization from '../../components/Graph/GraphVisualization';

export const metadata = {
  title: 'Knowledge Graph | Atom',
  description: 'Visualize and manage your semantic knowledge base with recursive GraphRAG.',
};

export default function GraphPage() {
  return (
    <main className="min-h-screen bg-gray-50 flex flex-col">
      <div className="flex-1 flex flex-col">
        <GraphVisualization />
      </div>
    </main>
  );
}
