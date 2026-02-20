/**
 * Location Screen - Location preferences and monitoring
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { locationService, LocationAccuracy, LocationInfo } from '../../services/locationService';

interface LocationScreenProps {
  navigation: any;
}

export const LocationScreen: React.FC<LocationScreenProps> = ({ navigation }) => {
  const [currentLocation, setCurrentLocation] = useState<LocationInfo | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const [isBackgroundTracking, setIsBackgroundTracking] = useState(false);
  const [accuracy, setAccuracy] = useState<LocationAccuracy>('high');
  const [loading, setLoading] = useState(false);
  const [permissionStatus, setPermissionStatus] = useState<{
    foreground: 'granted' | 'denied' | 'undetermined';
    background: 'granted' | 'denied' | 'undetermined';
  }>({ foreground: 'undetermined', background: 'undetermined' });

  useEffect(() => {
    initializeScreen();
  }, []);

  const initializeScreen = async () => {
    try {
      setLoading(true);

      // Check permissions
      const permissions = await locationService.getPermissionStatus();
      setPermissionStatus(permissions);

      // Get current location if permission granted
      if (permissions.foreground === 'granted') {
        const location = await locationService.getCurrentLocation();
        setCurrentLocation(location);

        const tracking = locationService.isActive();
        setIsTracking(tracking);
        setIsBackgroundTracking(locationService.isBackgroundTrackingActive());
      }
    } catch (error) {
      console.error('Failed to initialize location screen:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGetCurrentLocation = async () => {
    setLoading(true);
    try {
      const location = await locationService.getCurrentLocation();
      setCurrentLocation(location);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleTracking = async () => {
    try {
      if (isTracking) {
        await locationService.stopTracking();
        setIsTracking(false);
        setIsBackgroundTracking(false);
      } else {
        const success = await locationService.startTracking();
        if (success) {
          setIsTracking(true);
        } else {
          Alert.alert('Error', 'Failed to start location tracking');
        }
      }
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const handleOpenSettings = async () => {
    await locationService.openSettings();
  };

  const handleClearHistory = async () => {
    Alert.alert(
      'Clear History',
      'Are you sure you want to clear location history?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            await locationService.clearLocationHistory();
            Alert.alert('Success', 'Location history cleared');
          },
        },
      ]
    );
  };

  const batteryUsage = locationService.getBatteryUsage();

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Location</Text>
        <Text style={styles.subtitle}>Track your location and manage preferences</Text>
      </View>

      <ScrollView style={styles.content}>
        {/* Current Location */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Current Location</Text>
          {currentLocation ? (
            <View>
              <Text style={styles.locationText}>
                Latitude: {currentLocation.latitude.toFixed(6)}
              </Text>
              <Text style={styles.locationText}>
                Longitude: {currentLocation.longitude.toFixed(6)}
              </Text>
              <Text style={styles.locationText}>
                Accuracy: ±{currentLocation.accuracy?.toFixed(0)} meters
              </Text>
            </View>
          ) : (
            <Text style={styles.placeholderText}>No location data</Text>
          )}
          <TouchableOpacity
            style={styles.button}
            onPress={handleGetCurrentLocation}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Get Current Location</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Tracking Control */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Location Tracking</Text>
          <View style={styles.row}>
            <Text style={styles.label}>Foreground Tracking</Text>
            <TouchableOpacity
              style={[styles.toggle, isTracking && styles.toggleActive]}
              onPress={handleToggleTracking}
            >
              <Text style={styles.toggleText}>{isTracking ? 'ON' : 'OFF'}</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.batteryText}>
            Battery Usage: {batteryUsage.toUpperCase()}
          </Text>
        </View>

        {/* Accuracy Settings */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Accuracy</Text>
          {(['low', 'balanced', 'high', 'best'] as LocationAccuracy[]).map((level) => (
            <TouchableOpacity
              key={level}
              style={[styles.radioOption, accuracy === level && styles.radioOptionActive]}
              onPress={() => {
                setAccuracy(level);
                locationService.setAccuracy(level);
              }}
            >
              <View style={styles.radioCircle}>
                {accuracy === level && <View style={styles.radioSelected} />}
              </View>
              <Text style={styles.radioText}>{level.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Permission Status */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Permissions</Text>
          <View style={styles.row}>
            <Text style={styles.label}>Foreground</Text>
            <View
              style={[
                styles.statusBadge,
                permissionStatus.foreground === 'granted'
                  ? styles.statusGranted
                  : styles.statusDenied,
              ]}
            >
              <Text style={styles.statusText}>{permissionStatus.foreground}</Text>
            </View>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Background</Text>
            <View
              style={[
                styles.statusBadge,
                permissionStatus.background === 'granted'
                  ? styles.statusGranted
                  : styles.statusDenied,
              ]}
            >
              <Text style={styles.statusText}>{permissionStatus.background}</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.button} onPress={handleOpenSettings}>
            <Text style={styles.buttonText}>Open Settings</Text>
          </TouchableOpacity>
        </View>

        {/* Clear History */}
        <TouchableOpacity style={styles.dangerButton} onPress={handleClearHistory}>
          <Ionicons name="trash-outline" size={20} color="#f44336" />
          <Text style={styles.dangerButtonText}>Clear Location History</Text>
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
  locationText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  placeholderText: {
    fontSize: 14,
    color: '#999',
    fontStyle: 'italic',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  label: {
    fontSize: 16,
    color: '#333',
  },
  toggle: {
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#ddd',
  },
  toggleActive: {
    backgroundColor: '#4CAF50',
  },
  toggleText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  batteryText: {
    fontSize: 12,
    color: '#999',
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
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusGranted: {
    backgroundColor: '#4CAF50',
  },
  statusDenied: {
    backgroundColor: '#f44336',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  button: {
    backgroundColor: '#2196F3',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 12,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  dangerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#f44336',
    marginTop: 8,
  },
  dangerButtonText: {
    color: '#f44336',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default LocationScreen;
