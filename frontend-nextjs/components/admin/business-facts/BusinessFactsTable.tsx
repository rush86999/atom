import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Edit, Trash2, FileText, Globe, Calendar } from "lucide-react";
import { CitationViewer } from "./CitationViewer";
import { VerificationStatusBadge } from "./VerificationStatusBadge";
import type { BusinessFact } from "@/types/jit-verification";

interface BusinessFactsTableProps {
  facts: BusinessFact[];
  onEdit: (fact: BusinessFact) => void;
  onDelete: (factId: string) => void;
}

/**
 * Business Facts Table
 *
 * Displays business facts in a sortable table with actions.
 */
export const BusinessFactsTable: React.FC<BusinessFactsTableProps> = ({
  facts,
  onEdit,
  onDelete,
}) => {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  if (facts.length === 0) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="text-center text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium mb-2">No facts found</p>
            <p className="text-sm">
              Try adjusting your filters or create a new business fact
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fact</TableHead>
              <TableHead>Domain</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Citations</TableHead>
              <TableHead>Last Verified</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {facts.map((fact) => (
              <>
                <TableRow
                  key={fact.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => setExpandedRow(expandedRow === fact.id ? null : fact.id)}
                >
                  <TableCell className="max-w-md">
                    <div className="flex items-start gap-2">
                      <FileText className="h-4 w-4 mt-1 flex-shrink-0 text-muted-foreground" />
                      <p className="text-sm line-clamp-2">{fact.fact}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Globe className="h-3 w-3 text-muted-foreground" />
                      <span className="text-sm">{fact.domain}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <VerificationStatusBadge status={fact.verification_status} />
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="font-mono text-xs">
                      {fact.citations.length}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      {formatDate(fact.last_verified)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      {formatDate(fact.created_at)}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEdit(fact);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(fact.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>

                {/* Expanded Row - Citation Viewer */}
                {expandedRow === fact.id && (
                  <TableRow>
                    <TableCell colSpan={7} className="bg-muted/30">
                      <div className="py-4 space-y-3">
                        <div>
                          <h4 className="text-sm font-medium mb-1">Reason</h4>
                          <p className="text-sm text-muted-foreground">{fact.reason}</p>
                        </div>
                        <CitationViewer citations={fact.citations} factId={fact.id} />
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
