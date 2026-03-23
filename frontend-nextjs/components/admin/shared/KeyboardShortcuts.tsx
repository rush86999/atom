import React, { useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Keyboard } from "lucide-react";

interface Shortcut {
  key: string;
  description: string;
  action: () => void;
}

interface ShortcutGroup {
  title: string;
  shortcuts: Shortcut[];
}

/**
 * Keyboard Shortcuts Handler
 *
 * Manages global keyboard shortcuts for the application.
 */
export const useKeyboardShortcuts = (groups: ShortcutGroup[]) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for modifier keys
      const isModifierKey = e.metaKey || e.ctrlKey || e.altKey;

      // Don't trigger if user is typing in an input
      const target = e.target as HTMLElement;
      const isInput = target.tagName === "INPUT" ||
                      target.tagName === "TEXTAREA" ||
                      target.contentEditable === "true";

      if (isInput && !isModifierKey) {
        return; // Don't trigger shortcuts when typing
      }

      // Find matching shortcut
      for (const group of groups) {
        for (const shortcut of group.shortcuts) {
          const keys = shortcut.key.split("+");

          const matches = keys.every((key) => {
            const normalizedKey = key.toLowerCase();
            if (normalizedKey === "ctrl" || normalizedKey === "cmd") {
              return e.ctrlKey || e.metaKey;
            }
            if (normalizedKey === "shift") {
              return e.shiftKey;
            }
            if (normalizedKey === "alt") {
              return e.altKey;
            }
            return e.key.toLowerCase() === normalizedKey;
          });

          if (matches) {
            e.preventDefault();
            shortcut.action();
            return;
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [groups]);
};

/**
 * Keyboard Shortcuts Help Dialog
 *
 * Displays all available keyboard shortcuts.
 */
interface KeyboardShortcutsHelpProps {
  open: boolean;
  onClose: () => void;
  groups: ShortcutGroup[];
}

export const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  open,
  onClose,
  groups,
}) => {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <Keyboard className="h-5 w-5 mr-2" />
            Keyboard Shortcuts
          </DialogTitle>
          <DialogDescription>
            Press <kbd className="px-1 py-0.5 rounded bg-muted text-xs">?</kbd> to open this dialog
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {groups.map((group, idx) => (
            <div key={idx}>
              <h4 className="text-sm font-medium mb-3">{group.title}</h4>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut, sIdx) => (
                  <div key={sIdx} className="flex items-center justify-between">
                    <span className="text-sm">{shortcut.description}</span>
                    <div className="flex items-center gap-1">
                      {shortcut.key.split("+").map((key, kIdx) => (
                        <React.Fragment key={kIdx}>
                          {kIdx > 0 && <span className="text-xs text-muted-foreground">+</span>}
                          <kbd className="px-2 py-1 text-xs font-mono rounded bg-muted border">
                            {key}
                          </kbd>
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-4 border-t">
          <button
            onClick={onClose}
            className="text-sm text-primary hover:underline"
          >
            Close
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
