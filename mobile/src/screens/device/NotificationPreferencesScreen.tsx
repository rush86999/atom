/**
 * Notification Preferences Screen - Notification preferences management
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Switch,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { notificationService } from '../../services/notificationService';

interface NotificationPreferencesScreenProps {
  navigation: any;
}

interface NotificationPreferences {
  enabled: boolean;
  agentAlerts: boolean;
  workflowUpdates: boolean;
  systemAlerts: boolean;
  sound: string;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  badgeEnabled: boolean;
}

export const NotificationPreferencesScreen: React.FC<NotificationPreferencesScreenProps> = ({
  navigation,
}) => {
  const [preferences, setPreferences] = useState<NotificationPreferences>({
    enabled: true,
    agentAlerts: true,
    workflowUpdates: true,
    systemAlerts: true,
    sound: 'default',
    quietHoursEnabled: false,
    quietHoursStart: '22:00',
    quietHoursEnd: '08:00',
    badgeEnabled: true,
  });
  const [permissionStatus, setPermissionStatus] = useState<'granted' | 'denied' | 'undetermined'>('undetermined');
  const [sendingPreview, setSendingPreview] = useState(false);

  useEffect(() => {
    initializeScreen();
  }, []);

  const initializeScreen = async () => {
    try {
      const status = await notificationService.getPermissionStatus();
      setPermissionStatus(status);
    } catch (error) {
      console.error('Failed to initialize notification screen:', error);
    }
  };

  const handleRequestPermission = async () => {
    try {
      const status = await notificationService.requestPermissions();
      setPermissionStatus(status);

      if (status === 'denied') {
        Alert.alert(
          'Permission Denied',
          'Notification permissions are required for this feature. Please enable them in your device settings.',
          [{ text: 'OK' }]
        );
      }
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handleSendPreview = async () => {
    setSendingPreview(true);
    try {
      await notificationService.sendLocalNotification({
        title: 'Atom Notification',
        body: 'This is a preview notification from Atom',
        sound: true,
        badge: 1,
      });
      Alert.alert('Success', 'Preview notification sent');
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setSendingPreview(false);
    }
  };

  const updatePreference = <K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K]
  ) => {
    setPreferences((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Notifications</Text>
        <Text style={styles.subtitle}>Manage your notification preferences</Text>
      </View>

      <ScrollView style={styles.content}>
        {/* Permission Status */}
        <View style={styles.card}>
          <View style={styles.row}>
            <View style={styles.rowLeft}>
              <Ionicons name="notifications" size={24} color="#2196F3" />
              <View style={styles.textContainer}>
                <Text style={styles.label}>Enable Notifications</Text>
                <Text style={styles.sublabel}>
                  {permissionStatus === 'granted'
                    ? 'Notifications are enabled'
                    : 'Grant permission to receive notifications'}
                </Text>
              </View>
            </View>
            <Switch
              value={permissionStatus === 'granted'}
              onValueChange={handleRequestPermission}
              trackColor={{ false: '#ddd', true: '#2196F3' }}
            />
          </View>
        </View>

        {/* Categories */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Categories</Text>

          {[
            { key: 'agentAlerts', label: 'Agent Alerts', icon: 'megaphone' },
            { key: 'workflowUpdates', label: 'Workflow Updates', icon: 'git-branch' },
            { key: 'systemAlerts', label: 'System Alerts', icon: 'warning' },
          ].map((category) => (
            <View key={category.key} style={styles.row}>
              <View style={styles.rowLeft}>
                <Ionicons name={category.key as any} size={20} color="#666" />
                <Text style={styles.label}>{category.label}</Text>
              </View>
              <Switch
                value={preferences[category.key as keyof NotificationPreferences] as boolean}
                onValueChange={(value) => updatePreference(category.key as keyof NotificationPreferences, value)}
                disabled={permissionStatus !== 'granted'}
                trackColor={{ false: '#ddd', true: '#2196F3' }}
              />
            </View>
          ))}
        </View>

        {/* Sound */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Sound</Text>
          {['default', 'chime', 'bell', 'silence'].map((sound) => (
            <TouchableOpacity
              key={sound}
              style={[styles.radioOption, preferences.sound === sound && styles.radioOptionActive]}
              onPress={() => updatePreference('sound', sound)}
            >
              <View style={styles.radioCircle}>
                {preferences.sound === sound && <View style={styles.radioSelected} />}
              </View>
              <Text style={styles.radioText}>{sound.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Quiet Hours */}
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.cardTitle}>Quiet Hours</Text>
            <Switch
              value={preferences.quietHoursEnabled}
              onValueChange={(value) => updatePreference('quietHoursEnabled', value)}
              trackColor={{ false: '#ddd', true: '#2196F3' }}
            />
          </View>
          {preferences.quietHoursEnabled && (
            <View style={styles.quietHoursContainer}>
              <View style={styles.timeRow}>
                <Text style={styles.timeLabel}>From</Text>
                <TouchableOpacity style={styles.timeButton}>
                  <Text style={styles.timeText}>{preferences.quietHoursStart}</Text>
                </TouchableOpacity>
              </View>
              <View style={styles.timeRow}>
                <Text style={styles.timeLabel}>To</Text>
                <TouchableOpacity style={styles.timeButton}>
                  <Text style={styles.timeText}>{preferences.quietHoursEnd}</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        {/* Badge */}
        <View style={styles.card}>
          <View style={styles.row}>
            <View style={styles.rowLeft}>
              <Ionicons name="apps" size={24} color="#2196F3" />
              <View style={styles.textContainer}>
                <Text style={styles.label}>App Icon Badge</Text>
                <Text style={styles.sublabel}>Show unread count on app icon</Text>
              </View>
            </View>
            <Switch
              value={preferences.badgeEnabled}
              onValueChange={(value) => updatePreference('badgeEnabled', value)}
              disabled={permissionStatus !== 'granted'}
              trackColor={{ false: '#ddd', true: '#2196F3' }}
            />
          </View>
        </View>

        {/* Preview */}
        <TouchableOpacity
          style={styles.button}
          onPress={handleSendPreview}
          disabled={sendingPreview || permissionStatus !== 'granted'}
        >
          {sendingPreview ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="send" size={20} color="#fff" />
              <Text style={styles.buttonText}>Send Preview Notification</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#2196F3',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255, 255, 255, 0.9)',
    marginTop: 4,
  },
  content: {
    flex: 1,
    padding: 20,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  rowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  textContainer: {
    marginLeft: 12,
  },
  label: {
    fontSize: 16,
    color: '#333',
  },
  sublabel: {
    fontSize: 12,
    color: '#999',
    marginTop: 2,
  },
  radioOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  radioOptionActive: {
    backgroundColor: '#f0f8ff',
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#2196F3',
    marginRight: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  radioSelected: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#2196F3',
  },
  radioText: {
    fontSize: 16,
  },
  quietHoursContainer: {
    marginTop: 12,
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  timeLabel: {
    fontSize: 16,
    color: '#666',
  },
  timeButton: {
    backgroundColor: '#f0f0f0',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  timeText: {
    fontSize: 16,
    fontWeight: '600',
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2196F3',
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default NotificationPreferencesScreen;
