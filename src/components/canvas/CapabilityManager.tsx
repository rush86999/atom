/**
 * Capability Manager Component
 *
 * Main container component for managing agent capabilities and business facts.
 */

'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Shield, Zap, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { CapabilityList } from './CapabilityList';
import { BusinessFactDisplay } from './BusinessFactDisplay';
import { CapabilityDetailModal } from './CapabilityDetailModal';
import {
  listCapabilities,
  listBusinessFacts,
  toggleCapability,
  deleteCapability,
  Capability,
  BusinessFact,
} from '@/lib/api/capability-client';

interface CapabilityManagerProps {
  agentId: string;
  agentName: string;
}

/**
 * Capability manager with tabs for capabilities and business facts
 *
 * @example
 * ```tsx
 * <CapabilityManager
 *   agentId="agent_123"
 *   agentName="FinanceAgent"
 * />
 * ```
 */
export function CapabilityManager({
  agentId,
  agentName,
}: CapabilityManagerProps) {
  // State
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [businessFacts, setBusinessFacts] = useState<BusinessFact[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCapability, setSelectedCapability] = useState<Capability | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'capabilities' | 'business-facts'>('capabilities');

  /**
   * Load capabilities and business facts
   */
  const loadData = async (showRefreshing = false) => {
    if (showRefreshing) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      // Load capabilities
      const capsResponse = await listCapabilities(agentId);
      setCapabilities(capsResponse.capabilities);

      // Load business facts
      const factsResponse = await listBusinessFacts();
      setBusinessFacts(factsResponse.facts);
    } catch (err) {
      console.error('[CapabilityManager] Failed to load data:', err);
      setError('Failed to load capabilities and business facts');
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  /**
   * Load data on mount
   */
  useEffect(() => {
    loadData();
  }, [agentId]);

  /**
   * Handle capability toggle
   */
  const handleToggleCapability = async (capabilityId: string, enabled: boolean) => {
    try {
      await toggleCapability(agentId, capabilityId, enabled);

      // Update local state
      setCapabilities((prev) =>
        prev.map((cap) =>
          cap.id === capabilityId ? { ...cap, is_enabled: enabled } : cap
        )
      );

      toast.success(`Capability ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      console.error('[CapabilityManager] Failed to toggle capability:', err);
      toast.error('Failed to toggle capability');
      throw err;
    }
  };

  /**
   * Handle delete capability
   */
  const handleDeleteCapability = async (capabilityId: string) => {
    try {
      await deleteCapability(agentId, capabilityId);

      // Update local state
      setCapabilities((prev) => prev.filter((cap) => cap.id !== capabilityId));

      toast.success('Capability deleted');
    } catch (err) {
      console.error('[CapabilityManager] Failed to delete capability:', err);
      toast.error('Failed to delete capability');
      throw err;
    }
  };

  /**
   * Handle view capability details
   */
  const handleViewDetails = (capability: Capability) => {
    setSelectedCapability(capability);
    setModalOpen(true);
  };

  /**
   * Handle refresh
   */
  const handleRefresh = () => {
    loadData(true);
  };

  /**
   * Get capability counts
   */
  const enabledCount = capabilities.filter((c) => c.is_enabled).length;
  const totalCount = capabilities.length;

  /**
   * Get enforced facts count
   */
  const enforcedCount = businessFacts.filter((f) => f.is_enforced).length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Capability Manager</h2>
          <p className="text-sm text-gray-400 mt-1">
            Manage capabilities and business rules for {agentName}
          </p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <Card className="p-4 bg-red-500/10 border-red-500/20">
          <div className="flex items-center gap-2 text-red-400">
            <Zap className="w-4 h-4" />
            <p className="text-sm">{error}</p>
          </div>
        </Card>
      )}

      {/* Loading state */}
      {loading ? (
        <Card className="p-8 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
            <p className="text-sm text-gray-400">Loading capabilities...</p>
          </div>
        </Card>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4">
            <Card className="p-4 glass-premium">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Capabilities</p>
                  <p className="text-2xl font-semibold mt-1">
                    {enabledCount} <span className="text-gray-500 text-lg">/ {totalCount}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {enabledCount === totalCount ? 'All enabled' : `${totalCount - enabledCount} disabled`}
                  </p>
                </div>
                <div className="p-3 bg-purple-500/20 rounded-lg">
                  <Zap className="w-6 h-6 text-purple-400" />
                </div>
              </div>
            </Card>

            <Card className="p-4 glass-premium">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Business Rules</p>
                  <p className="text-2xl font-semibold mt-1">{enforcedCount}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {enforcedCount === businessFacts.length
                      ? 'All enforced'
                      : `${businessFacts.length - enforcedCount} not enforced`}
                  </p>
                </div>
                <div className="p-3 bg-blue-500/20 rounded-lg">
                  <Shield className="w-6 h-6 text-blue-400" />
                </div>
              </div>
            </Card>
          </div>

          {/* Tabs */}
          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as 'capabilities' | 'business-facts')}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="capabilities" className="gap-2">
                <Zap className="w-4 h-4" />
                Capabilities
                <Badge variant="secondary" className="ml-1">
                  {totalCount}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="business-facts" className="gap-2">
                <Shield className="w-4 h-4" />
                Business Rules
                <Badge variant="secondary" className="ml-1">
                  {enforcedCount}
                </Badge>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="capabilities" className="mt-4">
              <CapabilityList
                agentId={agentId}
                capabilities={capabilities}
                onToggle={handleToggleCapability}
                onViewDetails={handleViewDetails}
                onRefresh={handleRefresh}
                loading={refreshing}
              />
            </TabsContent>

            <TabsContent value="business-facts" className="mt-4">
              <BusinessFactDisplay
                facts={businessFacts}
                onRefresh={handleRefresh}
                loading={refreshing}
              />
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Capability Detail Modal */}
      <CapabilityDetailModal
        capability={selectedCapability}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onToggle={handleToggleCapability}
        onDelete={handleDeleteCapability}
      />
    </div>
  );
}

export default CapabilityManager;
