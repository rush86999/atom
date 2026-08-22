/**
 * Integrations Section (Settings)
 *
 * Round 80: the mobile app had zero integration visibility — this adds a
 * read-only connection-status section backed by GET /api/v1/integrations/health
 * and GET /api/integrations.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Linking,
  AppState,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getIntegrationHealth,
  getOAuthAuthorizeUrl,
  disconnectIntegration,
  AllIntegrationsHealth,
} from '../../services/integrationService';

/** Providers whose stored OAuth tokens can be revoked from mobile (v1.5). */
const DISCONNECTABLE_PROVIDERS = new Set([
  'google', 'microsoft', 'salesforce', 'slack', 'github',
  'asana', 'notion', 'trello', 'dropbox', 'whatsapp', 'zoho',
]);

interface IntegrationsSectionProps {
  expanded?: boolean;
  onToggle?: () => void;
}

export const IntegrationsSection: React.FC<IntegrationsSectionProps> = ({
  expanded = false,
  onToggle,
}) => {
  const [health, setHealth] = useState<AllIntegrationsHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getIntegrationHealth());
    } catch (e: any) {
      setError(e?.message || 'Failed to load integrations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const healthy = health?.healthy_integrations ?? 0;
  const total = health?.total_integrations ?? 0;
  const disconnectable = (name: string) =>
    DISCONNECTABLE_PROVIDERS.has(name.toLowerCase());

  const handleConnect = async (provider: string) => {
    setConnecting(provider);
    setError(null);
    try {
      const url = await getOAuthAuthorizeUrl(provider);
      await Linking.openURL(url);
    } catch (e: any) {
      setError(e?.message || 'Failed to start connection');
    } finally {
      setConnecting(null);
    }
  };

  // Re-check health when the user returns from the system browser
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        load();
      }
    });
    return () => sub.remove();
  }, [load]);

  const handleDisconnect = async (provider: string) => {
    setDisconnecting(provider);
    setError(null);
    try {
      await disconnectIntegration(provider);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to disconnect');
    } finally {
      setDisconnecting(null);
    }
  };

  const renderRow = ({ item }: { item: any }) => (
    <View style={styles.row} testID={`integration-row-${item.service_name}`}>
      <Text style={styles.rowName}>{item.service_name}</Text>
      <View style={styles.rowRight}>
        <View
          style={[
            styles.badge,
            item.status === 'healthy' ? styles.badgeHealthy : styles.badgeUnhealthy,
          ]}
        >
          <Text style={styles.badgeText}>{item.status}</Text>
        </View>
        {disconnectable(item.service_name) && item.status === 'healthy' && (
          <TouchableOpacity
            style={styles.disconnectButton}
            onPress={() => handleDisconnect(item.service_name)}
            disabled={disconnecting === item.service_name}
            testID={`disconnect-${item.service_name}`}
          >
            <Text style={styles.disconnectText}>
              {disconnecting === item.service_name ? '…' : 'Disconnect'}
            </Text>
          </TouchableOpacity>
        )}
        {disconnectable(item.service_name) && item.status !== 'healthy' && (
          <TouchableOpacity
            style={styles.connectButton}
            onPress={() => handleConnect(item.service_name)}
            disabled={connecting === item.service_name}
            testID={`connect-${item.service_name}`}
          >
            <Text style={styles.connectText}>
              {connecting === item.service_name ? '…' : 'Connect'}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.header}
        onPress={onToggle}
        testID="integrations-section-header"
      >
        <Ionicons name="grid-outline" size={22} color="#2196F3" />
        <View style={styles.headerText}>
          <Text style={styles.title}>Integrations</Text>
          <Text style={styles.subtitle}>
            {loading ? 'Checking…' : `${healthy} of ${total} healthy`}
          </Text>
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={18}
          color="#888"
        />
      </TouchableOpacity>

      {error && <Text style={styles.error}>{error}</Text>}

      {expanded && loading && <ActivityIndicator testID="integrations-loading" />}

      {expanded && !loading && health && (
        <FlatList
          data={health.integration_status}
          keyExtractor={(item) => item.service_name}
          renderItem={renderRow}
          initialNumToRender={12}
          style={styles.list}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: '#fff',
    borderRadius: 8,
  },
  headerText: {
    flex: 1,
    marginLeft: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a1a',
  },
  subtitle: {
    fontSize: 13,
    color: '#666',
    marginTop: 2,
  },
  error: {
    color: '#c0392b',
    fontSize: 13,
    paddingHorizontal: 16,
    paddingTop: 6,
  },
  list: {
    maxHeight: 320,
    paddingHorizontal: 16,
    paddingTop: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#eee',
  },
  rowName: {
    fontSize: 14,
    color: '#333',
    textTransform: 'capitalize',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  badgeHealthy: {
    backgroundColor: '#e6f7ed',
  },
  badgeUnhealthy: {
    backgroundColor: '#fdecea',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#333',
    textTransform: 'uppercase',
  },
  rowRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  disconnectButton: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: '#fdecea',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#e57373',
  },
  disconnectText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#c0392b',
  },
  connectButton: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: '#e6f7ed',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#4caf50',
  },
  connectText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#2e7d32',
  },
});
