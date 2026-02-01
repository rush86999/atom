/**
 * Mobile Metrics Cards Component
 * Touch-friendly KPI cards for mobile analytics
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { MetricCardData } from '../types/analytics';

interface MetricsCardsProps {
  data: MetricCardData[];
  onPress?: (index: number) => void;
}

export const MetricsCards: React.FC<MetricsCardsProps> = ({ data, onPress }) => {
  const getColor = (color?: string): string => {
    const colors: Record<string, string> = {
      success: '#4CAF50',
      warning: '#FF9800',
      error: '#f44336',
      info: '#2196F3',
    };
    return colors[color || 'info'] || '#2196F3';
  };

  const getTrendIcon = (trend?: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up':
        return <Ionicons name="trending-up" size={16} color="#4CAF50" />;
      case 'down':
        return <Ionicons name="trending-down" size={16} color="#f44336" />;
      default:
        return <Ionicons name="remove" size={16} color="#757575" />;
    }
  };

  return (
    <View style={styles.container}>
      {data.map((item, index) => (
        <TouchableOpacity
          key={index}
          style={[styles.card, { borderLeftColor: getColor(item.color) }]}
          onPress={() => onPress?.(index)}
          activeOpacity={0.7}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconContainer, { backgroundColor: `${getColor(item.color)}20` }]}>
              <Ionicons name="stats-chart" size={24} color={getColor(item.color)} />
            </View>
            {item.trend && <View style={styles.trendContainer}>{getTrendIcon(item.trend)}</View>}
          </View>

          <Text style={styles.value}>{item.value}</Text>
          <Text style={styles.title}>{item.title}</Text>

          {item.description && (
            <Text style={styles.description}>{item.description}</Text>
          )}

          {item.trendValue && (
            <View style={styles.trendValueContainer}>
              <Text style={styles.trendValue}>{item.trendValue}</Text>
            </View>
          )}
        </TouchableOpacity>
      ))}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  card: {
    width: '50%',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    margin: 6,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  trendContainer: {
    padding: 4,
  },
  value: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  title: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  description: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  trendValueContainer: {
    marginTop: 8,
  },
  trendValue: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
});

export default MetricsCards;
