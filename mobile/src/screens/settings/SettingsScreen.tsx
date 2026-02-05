/**
 * SettingsScreen - App Settings and Preferences
 *
 * Provides access to:
 * - User profile settings
 * - App preferences (theme, notifications)
 * - Device management
 * - Logout
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../contexts/AuthContext';
import { useDevice } from '../../contexts/DeviceContext';

interface SettingItem {
  id: string;
  icon: string;
  title: string;
  description?: string;
  type: 'toggle' | 'navigation' | 'action';
  value?: boolean;
  onPress?: () => void;
}

export const SettingsScreen: React.FC = () => {
  const { user, logout } = useAuth();
  const { deviceState, requestCapability } = useDevice();

  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [biometricEnabled, setBiometricEnabled] = useState(false);

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            await logout();
          },
        },
      ]
    );
  };

  const handleToggleNotifications = async (value: boolean) => {
    if (value) {
      const granted = await requestCapability('notifications');
      if (granted) {
        setNotificationsEnabled(true);
      } else {
        Alert.alert(
          'Permission Denied',
          'Notification permission is required to enable notifications'
        );
      }
    } else {
      setNotificationsEnabled(false);
    }
  };

  const handleToggleBiometric = async (value: boolean) => {
    if (value) {
      const granted = await requestCapability('biometric');
      if (granted) {
        setBiometricEnabled(true);
      } else {
        Alert.alert(
          'Biometric Not Available',
          'This device does not support biometric authentication or you have not enrolled a fingerprint/Face ID'
        );
      }
    } else {
      setBiometricEnabled(false);
    }
  };

  const settings: SettingItem[] = [
    {
      id: 'profile',
      icon: 'person-outline',
      title: 'Profile',
      description: user?.email || 'Not logged in',
      type: 'navigation',
    },
    {
      id: 'notifications',
      icon: 'notifications-outline',
      title: 'Notifications',
      description: 'Enable push notifications',
      type: 'toggle',
      value: notificationsEnabled,
    },
    {
      id: 'biometric',
      icon: 'finger-print-outline',
      title: 'Biometric Authentication',
      description: 'Use Face ID or Touch ID to login',
      type: 'toggle',
      value: biometricEnabled,
    },
    {
      id: 'device',
      icon: 'phone-portrait-outline',
      title: 'Device Info',
      description: `${deviceState.platform} - ${deviceState.deviceId?.substring(0, 8)}...`,
      type: 'navigation',
    },
    {
      id: 'about',
      icon: 'information-circle-outline',
      title: 'About',
      description: 'Atom v1.0.0',
      type: 'navigation',
    },
  ];

  const renderSettingItem = (item: SettingItem) => {
    if (item.type === 'toggle') {
      return (
        <TouchableOpacity
          key={item.id}
          style={styles.settingItem}
          onPress={() => {
            if (item.id === 'notifications') {
              handleToggleNotifications(!item.value);
            } else if (item.id === 'biometric') {
              handleToggleBiometric(!item.value);
            }
          }}
        >
          <View style={styles.settingItemLeft}>
            <Ionicons name={item.icon as any} size={24} color="#2196F3" />
            <View style={styles.settingItemText}>
              <Text style={styles.settingTitle}>{item.title}</Text>
              {item.description && (
                <Text style={styles.settingDescription}>{item.description}</Text>
              )}
            </View>
          </View>
          <Switch
            value={item.value}
            onValueChange={(value) => {
              if (item.id === 'notifications') {
                handleToggleNotifications(value);
              } else if (item.id === 'biometric') {
                handleToggleBiometric(value);
              }
            }}
            trackColor={{ false: '#ccc', true: '#2196F3' }}
            thumbColor="#fff"
          />
        </TouchableOpacity>
      );
    }

    return (
      <TouchableOpacity
        key={item.id}
        style={styles.settingItem}
        onPress={() => {
          if (item.id === 'logout') {
            handleLogout();
          }
        }}
      >
        <View style={styles.settingItemLeft}>
          <Ionicons
            name={item.icon as any}
            size={24}
            color={item.id === 'logout' ? '#f44336' : '#2196F3'}
          />
          <View style={styles.settingItemText}>
            <Text
              style={[
                styles.settingTitle,
                item.id === 'logout' && styles.logoutText,
              ]}
            >
              {item.title}
            </Text>
            {item.description && (
              <Text style={styles.settingDescription}>{item.description}</Text>
            )}
          </View>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#999" />
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Settings</Text>
      </View>

      <ScrollView style={styles.content}>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          {settings.slice(0, 1).map(renderSettingItem)}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Preferences</Text>
          {settings.slice(1, 3).map(renderSettingItem)}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Device</Text>
          {settings.slice(3, 5).map(renderSettingItem)}
        </View>

        <View style={styles.section}>
          <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
            <Ionicons name="log-out-outline" size={24} color="#f44336" />
            <Text style={styles.logoutButtonText}>Logout</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.version}>Atom v1.0.0</Text>
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
    paddingTop: 60,
    paddingBottom: 20,
    paddingHorizontal: 20,
  },
  headerTitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
  },
  content: {
    flex: 1,
  },
  section: {
    backgroundColor: '#fff',
    marginTop: 20,
    paddingVertical: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
    paddingHorizontal: 20,
    paddingBottom: 10,
    textTransform: 'uppercase',
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  settingItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  settingItemText: {
    marginLeft: 15,
    flex: 1,
  },
  settingTitle: {
    fontSize: 16,
    fontWeight: '500',
    color: '#333',
  },
  settingDescription: {
    fontSize: 14,
    color: '#999',
    marginTop: 2,
  },
  logoutText: {
    color: '#f44336',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
    marginHorizontal: 20,
    marginVertical: 10,
    paddingVertical: 15,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#f44336',
  },
  logoutButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#f44336',
    marginLeft: 10,
  },
  version: {
    fontSize: 12,
    color: '#999',
    textAlign: 'center',
    paddingVertical: 20,
  },
});
