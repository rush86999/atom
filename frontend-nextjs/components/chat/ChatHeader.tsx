'use client';

import React from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Check, X, Edit2 } from "lucide-react";

interface ChatHeaderProps {
    sessionTitle: string;
    sessionId: string | null;
    isEditingTitle: boolean;
    tempTitle: string;
    setTempTitle: (title: string) => void;
    setIsEditingTitle: (isEditing: boolean) => void;
    handleTitleSave: () => Promise<void>;
    onRenameClick: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
    sessionTitle,
    sessionId,
    isEditingTitle,
    tempTitle,
    setTempTitle,
    setIsEditingTitle,
    handleTitleSave,
    onRenameClick,
}) => {
    return (
        <div className="p-4 border-b border-border flex justify-between items-center bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div>
                {isEditingTitle ? (
                    <div className="flex items-center gap-1">
                        <Input
                            value={tempTitle}
                            onChange={(e) => setTempTitle(e.target.value)}
                            className="h-8 w-64"
                            autoFocus
                            onKeyDown={(e) => {
                                if (e.key === "Enter") handleTitleSave();
                                if (e.key === "Escape") setIsEditingTitle(false);
                            }}
                        />
                        <Button 
                            size="icon" 
                            variant="ghost" 
                            className="h-8 w-8 text-green-500 hover:text-green-600 hover:bg-green-100/10" 
                            onClick={handleTitleSave}
                        >
                            <Check className="h-4 w-4" />
                        </Button>
                        <Button 
                            size="icon" 
                            variant="ghost" 
                            className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-100/10" 
                            onClick={() => setIsEditingTitle(false)}
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                ) : (
                    <div className="group flex items-center gap-2">
                        <div>
                            <h2 className="font-semibold">{sessionTitle}</h2>
                            <p className="text-xs text-muted-foreground">ID: {sessionId || "New Session"}</p>
                        </div>
                        <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-primary hover:bg-muted"
                            onClick={onRenameClick}
                        >
                            <Edit2 className="h-4 w-4" />
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};
