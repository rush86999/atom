atom/src/ui-shared/components/ThemeDemo.tsx
import React from 'react';
import { useTheme, useThemeColors } from '../contexts/ThemeContext';

export const ThemeDemo: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const colors = useThemeColors();

  return (
    <div className="card p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Black Metallic Design System</h2>
        <button
          onClick={toggleTheme}
          className="btn btn-metallic px-4 py-2"
        >
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'} Mode
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Color Palette */}
        <div className="card space-y-4">
          <h3 className="text-lg font-medium">Color Palette</h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-primary p-3 rounded text-center text-white">
              Primary
            </div>
            <div className="bg-secondary p-3 rounded text-center">
              Secondary
            </div>
            <div className="bg-accent p-3 rounded text-center text-white">
              Accent
            </div>
            <div className="bg-surface p-3 rounded text-center">
              Surface
            </div>
            <div className="bg-card p-3 rounded text-center">
              Card
            </div>
            <div className="bg-background p-3 rounded text-center border">
              Background
            </div>
          </div>
        </div>

        {/* Status Colors */}
        <div className="card space-y-4">
          <h3 className="text-lg font-medium">Status Colors</h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-success p-3 rounded text-center text-white">
              Success
            </div>
            <div className="bg-warning p-3 rounded text-center text-white">
              Warning
            </div>
            <div className="bg-error p-3 rounded text-center text-white">
              Error
            </div>
            <div className="bg-info p-3 rounded text-center text-white">
              Info
            </div>
          </div>
        </div>

        {/* Metallic Elements */}
        <div className="card-metallic p-4 space-y-4">
          <h3 className="text-lg font-medium">Metallic Elements</h3>
          <div className="space-y-2">
            <div className="bg-metallic-primary p-3 rounded text-center">
              Primary Metallic
            </div>
            <div className="bg-metallic-secondary p-3 rounded text-center">
              Secondary Metallic
            </div>
            <div className="bg-metallic-accent p-3 rounded text-center">
              Accent Metallic
            </div>
          </div>
        </div>

        {/* Interactive Elements */}
        <div className="card space-y-4">
          <h3 className="text-lg font-medium">Interactive Elements</h3>
          <div className="space-y-2">
            <button className="btn btn-primary w-full">
              Primary Button
            </button>
            <button className="btn btn-secondary w-full">
              Secondary Button
            </button>
            <button className="btn btn-metallic w-full">
              Metallic Button
            </button>
          </div>
        </div>
      </div>

      {/* Current Theme Info */}
      <div className="card p-4">
        <h3 className="text-lg font-medium mb-2">Current Theme: {theme}</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <strong>Background:</strong>
            <div className="w-4 h-4 inline-block ml-2 border" style={{ backgroundColor: colors.background }} />
          </div>
          <div>
            <strong>Text:</strong>
            <div className="w-4 h-4 inline-block ml-2 border" style={{ backgroundColor: colors.text }} />
          </div>
          <div>
            <strong>Primary:</strong>
            <div className="w-4 h-4 inline-block ml-2 border" style={{ backgroundColor: colors.primary }} />
          </div>
          <div>
            <strong>Border:</strong>
            <div className="w-4 h-4 inline-block ml-2 border" style={{ backgroundColor: colors.border }} />
          </div>
        </div>
      </div>

      <div className="text-center text-muted text-sm">
        This component demonstrates the shared black metallic design system
        that works in both NextJS and Desktop applications.
      </div>
    </div>
  );
};

export default ThemeDemo;
