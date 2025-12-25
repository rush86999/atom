import React from 'react';
import { getBezierPath, EdgeProps, BaseEdge, EdgeLabelRenderer } from 'reactflow';
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export default function AddStepEdge({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    data,
}: EdgeProps) {
    const [edgePath, labelX, labelY] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    const onAddStep = (event: React.MouseEvent) => {
        event.stopPropagation();
        if (data?.onAddStep) {
            data.onAddStep(id);
        }
    };

    return (
        <>
            <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                        fontSize: 12,
                        pointerEvents: 'all',
                    }}
                    className="nodrag nopan"
                >
                    <Button
                        variant="outline"
                        size="icon"
                        className="w-6 h-6 rounded-full bg-white border-2 border-primary hover:bg-primary hover:text-white transition-all shadow-sm flex items-center justify-center p-0"
                        onClick={onAddStep}
                        title="Add step here"
                    >
                        <Plus className="w-3 h-3" />
                    </Button>
                </div>
            </EdgeLabelRenderer>
        </>
    );
}
