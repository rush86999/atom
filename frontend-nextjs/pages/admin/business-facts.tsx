import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, RefreshCw, Search, Keyboard } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { businessFactsAPI } from "@/lib/api-admin";
import { AdminPoller } from "@/lib/api-admin";
import { BusinessFactsTable } from "@/components/admin/business-facts/BusinessFactsTable";
import { FactFilters } from "@/components/admin/business-facts/FactFilters";
import { BusinessFactForm } from "@/components/admin/business-facts/BusinessFactForm";
import {
  ErrorBoundary,
  OfflineIndicator,
  EmptyState,
  useKeyboardShortcuts,
  KeyboardShortcutsHelp,
} from "@/components/admin/shared";
import type {
  BusinessFact,
  BusinessFactFilters,
} from "@/types/jit-verification";

/**
 * Business Facts Management Page
 *
 * Provides CRUD operations for managing business facts with citation verification.
 */
const BusinessFactsPageContent: React.FC = () => {
  const [facts, setFacts] = useState<BusinessFact[]>([]);
  const [filteredFacts, setFilteredFacts] = useState<BusinessFact[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState<BusinessFactFilters>({
    status: "all",
    domain: "",
    limit: 100,
  });
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingFact, setEditingFact] = useState<BusinessFact | null>(null);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const { toast } = useToast();

  const poller = new AdminPoller();

  // Fetch all facts
  const fetchFacts = async () => {
    try {
      const response = await businessFactsAPI.listFacts(filters);
      setFacts(response.data.facts);
    } catch (error: any) {
      console.error("Failed to fetch facts:", error);
      toast({
        title: "Error loading facts",
        description: error.userMessage || "Failed to load business facts",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchFacts();
  }, [filters]);

  // Filter facts based on search query
  useEffect(() => {
    if (!searchQuery) {
      setFilteredFacts(facts);
    } else {
      const query = searchQuery.toLowerCase();
      setFilteredFacts(
        facts.filter(
          (fact) =>
            fact.fact.toLowerCase().includes(query) ||
            fact.domain.toLowerCase().includes(query) ||
            fact.reason.toLowerCase().includes(query)
        )
      );
    }
  }, [facts, searchQuery]);

  // Handle filter change
  const handleFilterChange = (newFilters: Partial<BusinessFactFilters>) => {
    setFilters({ ...filters, ...newFilters });
  };

  // Handle search
  const handleSearch = (value: string) => {
    setSearchQuery(value);
  };

  // Manual refresh
  const handleRefresh = () => {
    setRefreshing(true);
    fetchFacts();
  };

  // Handle create fact
  const handleCreateFact = () => {
    setShowCreateDialog(true);
  };

  // Handle edit fact
  const handleEditFact = (fact: BusinessFact) => {
    setEditingFact(fact);
  };

  // Handle delete fact
  const handleDeleteFact = async (factId: string) => {
    if (!confirm("Are you sure you want to delete this fact?")) {
      return;
    }

    try {
      await businessFactsAPI.deleteFact(factId);
      toast({
        title: "Fact deleted",
        description: "Business fact has been deleted successfully",
      });
      fetchFacts();
    } catch (error: any) {
      console.error("Failed to delete fact:", error);
      toast({
        title: "Delete failed",
        description: error.userMessage || "Failed to delete business fact",
        variant: "destructive",
      });
    }
  };

  // Handle form submit (create or update)
  const handleFormSubmit = () => {
    setShowCreateDialog(false);
    setEditingFact(null);
    fetchFacts();
  };

  // Handle form cancel
  const handleFormCancel = () => {
    setShowCreateDialog(false);
    setEditingFact(null);
  };

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      title: "Actions",
      shortcuts: [
        {
          key: "?",
          description: "Show keyboard shortcuts",
          action: () => setShowKeyboardHelp(true),
        },
        {
          key: "n",
          description: "Create new fact",
          action: handleCreateFact,
        },
        {
          key: "r",
          description: "Refresh facts",
          action: handleRefresh,
        },
        {
          key: "/",
          description: "Focus search",
          action: () => {
            const searchInput = document.querySelector("input[placeholder*='Search']") as HTMLInputElement;
            searchInput?.focus();
          },
        },
      ],
    },
  ]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <React.Fragment>
      <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Business Facts</h1>
          <p className="text-muted-foreground mt-1">
            Manage business facts with citation verification
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowKeyboardHelp(true)}
          >
            <Keyboard className="h-4 w-4 mr-2" />
            Shortcuts
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleCreateFact}>
            <Plus className="h-4 w-4 mr-2" />
            New Fact
          </Button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search facts, domains, or reasons..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        <FactFilters
          filters={filters}
          onFilterChange={handleFilterChange}
          domains={Array.from(new Set(facts.map((f) => f.domain)))}
        />
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold">{facts.length}</p>
              <p className="text-sm text-muted-foreground">Total Facts</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">
                {facts.filter((f) => f.verification_status === "verified").length}
              </p>
              <p className="text-sm text-muted-foreground">Verified</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-600">
                {facts.filter((f) => f.verification_status === "unverified").length}
              </p>
              <p className="text-sm text-muted-foreground">Unverified</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600">
                {facts.filter((f) => f.verification_status === "outdated").length}
              </p>
              <p className="text-sm text-muted-foreground">Outdated</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Facts Table */}
      <BusinessFactsTable
        facts={filteredFacts}
        onEdit={handleEditFact}
        onDelete={handleDeleteFact}
      />

      {/* Create/Edit Dialog */}
      {(showCreateDialog || editingFact) && (
        <BusinessFactForm
          fact={editingFact}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
        />
      )}
    </div>

    {/* Keyboard Shortcuts Help */}
    <KeyboardShortcutsHelp
        open={showKeyboardHelp}
        onClose={() => setShowKeyboardHelp(false)}
        groups={[
          {
            title: "Actions",
            shortcuts: [
              { key: "?", description: "Show keyboard shortcuts", action: () => {} },
              { key: "n", description: "Create new fact", action: () => {} },
              { key: "r", description: "Refresh facts", action: () => {} },
              { key: "/", description: "Focus search", action: () => {} },
            ],
          },
        ]}
      />
    </React.Fragment>
  );
};

// Wrapper with ErrorBoundary and OfflineIndicator
const BusinessFactsPageWrapper: React.FC = () => {
  return (
    <ErrorBoundary>
      <BusinessFactsPageContent />
      <OfflineIndicator />
    </ErrorBoundary>
  );
};

export default BusinessFactsPageWrapper;
