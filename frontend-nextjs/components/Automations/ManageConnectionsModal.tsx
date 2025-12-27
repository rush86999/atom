import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    Trash2,
    Edit2,
    Check,
    X,
    AlertCircle,
    Clock,
    Shield,
    Activity,
    Settings2,
    Loader2
} from 'lucide-react';
import { useToast } from "@/components/ui/use-toast";
import { motion, AnimatePresence } from 'framer-motion';

interface Connection {
    id: string;
    name: string;
    status: 'active' | 'error' | 'expired';
    created_at: string;
    last_used: string | null;
}

interface ManageConnectionsModalProps {
    isOpen: boolean;
    onClose: () => void;
    integrationId: string;
    integrationName: string;
    onConnectionsUpdated: () => void;
}

const ManageConnectionsModal: React.FC<ManageConnectionsModalProps> = ({
    isOpen,
    onClose,
    integrationId,
    integrationName,
    onConnectionsUpdated
}) => {
    const [connections, setConnections] = useState<Connection[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editName, setEditName] = useState("");
    const [isUpdating, setIsUpdating] = useState(false);
    const { toast } = useToast();

    const fetchConnections = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/connections?integration_id=${encodeURIComponent(integrationId)}`);
            if (response.ok) {
                const data = await response.json();
                setConnections(data);
            }
        } catch (error) {
            console.error("Failed to fetch connections:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen && integrationId) {
            fetchConnections();
        }
    }, [isOpen, integrationId]);

    const handleRename = async (connectionId: string) => {
        if (!editName.trim()) return;
        setIsUpdating(true);
        try {
            const response = await fetch(`/api/v1/connections/${connectionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: editName })
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Connection renamed successfully",
                });
                setEditingId(null);
                fetchConnections();
                onConnectionsUpdated();
            } else {
                throw new Error("Failed to rename");
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to rename connection",
                variant: "error"
            });
        } finally {
            setIsUpdating(false);
        }
    };

    const handleDelete = async (connectionId: string) => {
        if (!confirm("Are you sure you want to delete this connection? Workflows using it may break.")) return;

        try {
            const response = await fetch(`/api/v1/connections/${connectionId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                toast({
                    title: "Deleted",
                    description: "Connection removed successfully",
                });
                fetchConnections();
                onConnectionsUpdated();
            } else {
                throw new Error("Failed to delete");
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to delete connection",
                variant: "error"
            });
        }
    };

    const startEditing = (conn: Connection) => {
        setEditingId(conn.id);
        setEditName(conn.name);
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl bg-white/95 backdrop-blur-xl border-white/20 shadow-2xl overflow-hidden rounded-3xl p-0">
                <div className="bg-gradient-to-br from-purple-600/10 via-blue-600/5 to-transparent p-8 pb-4">
                    <DialogHeader>
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-white rounded-xl shadow-sm border border-purple-100">
                                <Settings2 className="w-5 h-5 text-purple-600" />
                            </div>
                            <DialogTitle className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-900 to-blue-900">
                                Manage {integrationName} Connections
                            </DialogTitle>
                        </div>
                        <DialogDescription className="text-gray-500 font-medium">
                            View, rename, or remove your authenticated accounts for this service.
                        </DialogDescription>
                    </DialogHeader>
                </div>

                <ScrollArea className="max-h-[500px] px-8 py-4">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-20 gap-4">
                            <Loader2 className="w-10 h-10 text-purple-600 animate-spin" />
                            <p className="text-sm font-medium text-gray-400">Loading connections...</p>
                        </div>
                    ) : connections.length === 0 ? (
                        <div className="text-center py-20 border-2 border-dashed border-gray-100 rounded-3xl">
                            <p className="text-gray-400 font-medium">No connections found for this integration.</p>
                        </div>
                    ) : (
                        <div className="space-y-4 pb-4">
                            <AnimatePresence>
                                {connections.map((conn) => (
                                    <motion.div
                                        key={conn.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        className="group relative p-5 bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md hover:border-purple-100 transition-all duration-300"
                                    >
                                        <div className="flex items-center justify-between gap-4">
                                            <div className="flex-1 space-y-2">
                                                {editingId === conn.id ? (
                                                    <div className="flex items-center gap-2 pr-12">
                                                        <Input
                                                            value={editName}
                                                            onChange={(e) => setEditName(e.target.value)}
                                                            className="h-9 font-semibold text-purple-900 border-purple-200 focus:ring-purple-500 rounded-lg"
                                                            autoFocus
                                                        />
                                                        <Button
                                                            size="icon"
                                                            variant="ghost"
                                                            className="h-9 w-9 text-green-600 hover:bg-green-50 rounded-lg"
                                                            onClick={() => handleRename(conn.id)}
                                                            disabled={isUpdating}
                                                        >
                                                            {isUpdating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-5 h-5" />}
                                                        </Button>
                                                        <Button
                                                            size="icon"
                                                            variant="ghost"
                                                            className="h-9 w-9 text-red-600 hover:bg-red-50 rounded-lg"
                                                            onClick={() => setEditingId(null)}
                                                        >
                                                            <X className="w-5 h-5" />
                                                        </Button>
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div className="flex items-center gap-3">
                                                            <h4 className="font-bold text-gray-900 tracking-tight">{conn.name}</h4>
                                                            <Badge
                                                                variant="outline"
                                                                className={`
                                                                    text-[10px] font-bold uppercase tracking-wider px-2 h-5
                                                                    ${conn.status === 'active' ? 'bg-green-50 text-green-600 border-green-100' :
                                                                        conn.status === 'error' ? 'bg-red-50 text-red-600 border-red-100' :
                                                                            'bg-amber-50 text-amber-600 border-amber-100'}
                                                                `}
                                                            >
                                                                {conn.status}
                                                            </Badge>
                                                        </div>
                                                        <div className="flex items-center gap-4 text-[11px] text-gray-400 font-medium">
                                                            <div className="flex items-center gap-1">
                                                                <Clock className="w-3 h-3" />
                                                                Added {new Date(conn.created_at).toLocaleDateString()}
                                                            </div>
                                                            {conn.last_used && (
                                                                <div className="flex items-center gap-1">
                                                                    <Activity className="w-3 h-3" />
                                                                    Active {new Date(conn.last_used).toLocaleDateString()}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </>
                                                )}
                                            </div>

                                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    className="h-9 w-9 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-xl"
                                                    onClick={() => startEditing(conn)}
                                                    title="Rename"
                                                >
                                                    <Edit2 className="w-4 h-4" />
                                                </Button>
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    className="h-9 w-9 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl"
                                                    onClick={() => handleDelete(conn.id)}
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    )}
                </ScrollArea>

                <div className="p-6 bg-gray-50/50 border-t border-gray-100 flex justify-between items-center rounded-b-3xl">
                    <div className="flex items-center gap-2 text-xs text-gray-400 font-medium">
                        <Shield className="w-3 h-3 text-purple-400" />
                        Credentials are encrypted at rest
                    </div>
                    <Button onClick={onClose} variant="secondary" className="font-bold rounded-xl px-6">
                        Done
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default ManageConnectionsModal;
