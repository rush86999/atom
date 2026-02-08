import type { CanvasSummary } from "../types";

interface CanvasListProps {
  canvases: CanvasSummary[];
}

export default function CanvasList({ canvases }: CanvasListProps) {
  if (canvases.length === 0) {
    return (
      <div style={{ padding: "12px", color: "#888", fontSize: "12px" }}>
        No recent canvases
      </div>
    );
  }

  return (
    <ul className="item-list">
      {canvases.map((canvas) => (
        <li key={canvas.id}>
          <div className="item-name">
            {canvas.canvas_type}
            {canvas.agent_name && <span> • {canvas.agent_name}</span>}
          </div>
          <div className="item-meta">
            {new Date(canvas.created_at).toLocaleString()}
          </div>
        </li>
      ))}
    </ul>
  );
}
