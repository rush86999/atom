/**
 * Approvals Screen
 *
 * Round 80s — mobile parity: HITL approval journey. Lists pending workflow
 * approvals (GET /api/agent-governance/pending-approvals) and lets a
 * supervisor approve or reject each one inline.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import {
  getPendingApprovals,
  approveWorkflow,
  rejectWorkflow,
  approvalId as idOf,
  PendingApproval,
} from '../../services/approvalsService';

interface ApprovalsScreenProps {
  onNavigateBack?: () => void;
}

export default function ApprovalsScreen({ onNavigateBack }: ApprovalsScreenProps) {
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setApprovals(await getPendingApprovals());
    } catch (e: any) {
      setError(e?.message || 'Failed to load approvals');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    load();
  }, [load]);

  const act = useCallback(
    async (item: PendingApproval, action: 'approve' | 'reject') => {
      const id = idOf(item);
      if (!id) return;
      setBusyId(id);
      setActionError(null);
      try {
        if (action === 'approve') {
          await approveWorkflow(id);
        } else {
          await rejectWorkflow(id);
        }
        // Optimistic removal — decision is recorded server-side.
        setApprovals((prev) => prev.filter((a) => idOf(a) !== id));
      } catch (e: any) {
        setActionError(e?.message || `Failed to ${action}`);
      } finally {
        setBusyId(null);
      }
    },
    []
  );

  const renderItem = ({ item }: { item: PendingApproval }) => {
    const id = idOf(item);
    const name =
      item.workflow_name || item.agent_name || `Approval ${id.slice(0, 8)}`;
    return (
      <View style={styles.card} testID={`approval-card-${id}`}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>{name}</Text>
          {item.maturity_level ? (
            <Text style={styles.badge}>{item.maturity_level}</Text>
          ) : null}
        </View>
        {item.agent_name ? (
          <Text style={styles.meta}>Agent: {item.agent_name}</Text>
        ) : null}
        {item.requested_by ? (
          <Text style={styles.meta}>Requested by {item.requested_by}</Text>
        ) : null}
        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.button, styles.rejectButton]}
            onPress={() => act(item, 'reject')}
            disabled={busyId === id}
            testID={`reject-${id}`}
          >
            <Text style={styles.rejectText}>
              {busyId === id ? '…' : 'Reject'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, styles.approveButton]}
            onPress={() => act(item, 'approve')}
            disabled={busyId === id}
            testID={`approve-${id}`}
          >
            <Text style={styles.approveText}>
              {busyId === id ? '…' : 'Approve'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container} testID="approvals-screen">
      <Text style={styles.title}>Approvals</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      {actionError && <Text style={styles.error}>{actionError}</Text>}

      {loading ? (
        <ActivityIndicator style={styles.spinner} testID="approvals-loading" />
      ) : approvals.length === 0 ? (
        <View style={styles.empty} testID="approvals-empty">
          <Text style={styles.emptyText}>No pending approvals.</Text>
          <Text style={styles.emptySub}>
            Workflow submissions needing sign-off will appear here.
          </Text>
        </View>
      ) : (
        <FlatList
          data={approvals}
          keyExtractor={(item, i) => idOf(item) || String(i)}
          renderItem={renderItem}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    padding: 16,
    color: '#1a1a1a',
  },
  error: {
    color: '#c0392b',
    fontSize: 13,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  spinner: {
    marginTop: 32,
  },
  empty: {
    alignItems: 'center',
    marginTop: 48,
    paddingHorizontal: 24,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  emptySub: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
    marginTop: 6,
  },
  list: {
    paddingHorizontal: 12,
    paddingBottom: 24,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1a1a1a',
    flexShrink: 1,
  },
  badge: {
    fontSize: 11,
    fontWeight: '600',
    color: '#2196F3',
    backgroundColor: '#e3f2fd',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    overflow: 'hidden',
    textTransform: 'uppercase',
  },
  meta: {
    fontSize: 12,
    color: '#777',
    marginTop: 4,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 10,
  },
  button: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 6,
  },
  rejectButton: {
    backgroundColor: '#fdecea',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#e57373',
  },
  rejectText: {
    color: '#c0392b',
    fontWeight: '600',
    fontSize: 13,
  },
  approveButton: {
    backgroundColor: '#e6f7ed',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#4caf50',
  },
  approveText: {
    color: '#2e7d32',
    fontWeight: '600',
    fontSize: 13,
  },
});
