import { useState, useCallback, useMemo } from 'react';
import { Node, Edge } from 'reactflow';

interface FlowState {
    nodes: Node[];
    edges: Edge[];
}

interface UseUndoRedoReturn {
    undo: () => void;
    redo: () => void;
    takeSnapshot: (state: FlowState) => void;
    canUndo: boolean;
    canRedo: boolean;
    history: {
        past: FlowState[];
        present: FlowState | null;
        future: FlowState[];
    };
    resetHistory: () => void;
}

export const useUndoRedo = (initialState: FlowState): UseUndoRedoReturn => {
    // History stack
    const [past, setPast] = useState<FlowState[]>([]);
    const [present, setPresent] = useState<FlowState>(initialState);
    const [future, setFuture] = useState<FlowState[]>([]);

    const canUndo = useMemo(() => past.length > 0, [past]);
    const canRedo = useMemo(() => future.length > 0, [future]);

    // Save a new state (clears future)
    const takeSnapshot = useCallback((newState: FlowState) => {
        setPast((prevPast) => {
            // Limit history size to 50
            const newPast = [...prevPast, present];
            return newPast.length > 50 ? newPast.slice(newPast.length - 50) : newPast;
        });
        setPresent(newState);
        setFuture([]);
    }, [present]);

    const undo = useCallback(() => {
        if (!canUndo) return;

        setPast((prevPast) => {
            const newPast = [...prevPast];
            const previousState = newPast.pop();

            if (previousState) {
                setFuture((prevFuture) => [present, ...prevFuture]);
                setPresent(previousState);
                return newPast;
            }
            return prevPast;
        });
    }, [canUndo, present]);

    const redo = useCallback(() => {
        if (!canRedo) return;

        setFuture((prevFuture) => {
            const newFuture = [...prevFuture];
            const nextState = newFuture.shift();

            if (nextState) {
                setPast((prevPast) => [...prevPast, present]);
                setPresent(nextState);
                return newFuture;
            }
            return prevFuture;
        });
    }, [canRedo, present]);

    const resetHistory = useCallback(() => {
        setPast([]);
        setFuture([]);
        setPresent(initialState);
    }, [initialState]);

    return {
        undo,
        redo,
        takeSnapshot,
        canUndo,
        canRedo,
        history: { past, present, future },
        resetHistory
    };
};
