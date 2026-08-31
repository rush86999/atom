import React, { useState } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";

interface HelpTooltipProps {
  content: string | React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

/**
 * Help Tooltip Component
 *
 * Displays helpful information in a tooltip.
 */
export const HelpTooltip: React.FC<HelpTooltipProps> = ({
  content,
  side = "top",
}) => {
  return (
    <TooltipProvider>
      {/* the local Tooltip/TooltipContent wrappers don't declare radix-style
          props, so pass them via a cast (runtime spreads/ignores them as before) */}
      <Tooltip {...({ delayDuration: 300 } as any)}>
        <TooltipTrigger asChild>
          <button className="inline-flex">
            <Info className="h-4 w-4 text-muted-foreground hover:text-foreground transition-colors" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          {...({ side } as any)}
          className="max-w-xs"
        >
          <p className="text-sm">{content}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
