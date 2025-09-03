atom / frontend - nextjs / components / ExampleSharedUsage.tsx;
import React from "react";
import { AISettingsModal } from "../../../src/ui-shared/components/AISettingsModal";
import { LLMProviderManager } from "../../../src/ui-shared/components/LLMProviderManager";
import { useAISettings } from "../../../src/ui-shared/hooks/useAISettings";
import { ThemeDemo } from "../../../src/ui-shared/components/ThemeDemo";
import { ThemeProvider } from "../../../src/ui-shared/contexts/ThemeContext";

/**
 * Example component demonstrating how to use shared UI components
 * This component can be used in both NextJS and Desktop apps
 */
export const ExampleSharedUsage: React.FC = () => {
  const { settings, updateSettings, isLoading } = useAISettings();

  const handleSettingsSave = async (newSettings: any) => {
    try {
      await updateSettings(newSettings);
      console.log("Settings saved successfully");
    } catch (error) {
      console.error("Failed to save settings:", error);
    }
  };

  return (
    <ThemeProvider>
      <div className="p-6 space-y-6 bg-background min-h-screen">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-primary mb-8">
            UI Feature Parity Demo
          </h1>

          {/* Theme Demo Section */}
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-secondary mb-4">
              Black Metallic Design System
            </h2>
            <ThemeDemo />
          </section>

          {/* AI Settings Section */}
          <section className="card p-6 space-y-4">
            <h2 className="text-2xl font-semibold text-secondary">
              AI Settings Components
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* AI Settings Modal */}
              <div className="card p-4">
                <h3 className="text-lg font-medium mb-3">Settings Modal</h3>
                <AISettingsModal
                  isOpen={false}
                  onClose={() => {}}
                  onSave={handleSettingsSave}
                  initialSettings={settings}
                />
                <p className="text-muted text-sm mt-2">
                  Same modal component used in both frontends
                </p>
              </div>

              {/* LLM Provider Manager */}
              <div className="card p-4">
                <h3 className="text-lg font-medium mb-3">Provider Manager</h3>
                <LLMProviderManager
                  providers={settings?.providers || []}
                  onProviderUpdate={(providerId, updates) => {
                    console.log("Provider updated:", providerId, updates);
                  }}
                  isLoading={isLoading}
                />
                <p className="text-muted text-sm mt-2">
                  Shared provider management interface
                </p>
              </div>
            </div>

            {/* Current Settings Display */}
            <div className="card p-4 bg-metallic-secondary">
              <h3 className="text-lg font-medium mb-2">Current AI Settings</h3>
              <div className="p-3 bg-card rounded">
                <pre className="text-sm text-muted overflow-x-auto">
                  {JSON.stringify(settings, null, 2)}
                </pre>
              </div>
            </div>
          </section>

          {/* Explanation Section */}
          <section className="card p-6 mt-8">
            <h2 className="text-xl font-semibold text-secondary mb-4">
              UI Feature Parity Achieved
            </h2>
            <div className="space-y-3 text-muted">
              <p>
                ✅ <strong>Shared Design System:</strong> Black metallic theme
                with dark/light modes
              </p>
              <p>
                ✅ <strong>Shared Components:</strong> AISettingsModal,
                LLMProviderManager, ThemeDemo
              </p>
              <p>
                ✅ <strong>Shared Hooks:</strong> useAISettings for consistent
                state management
              </p>
              <p>
                ✅ <strong>Shared Context:</strong> ThemeProvider for unified
                theming
              </p>
              <p>
                ✅ <strong>Consistent Styling:</strong> CSS utilities work in
                both environments
              </p>
              <p>
                ✅ <strong>Type Safety:</strong> Shared TypeScript definitions
              </p>
            </div>
          </section>
        </div>
      </div>
    </ThemeProvider>
  );
};

export default ExampleSharedUsage;
