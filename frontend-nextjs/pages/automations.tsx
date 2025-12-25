import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Play, LayoutTemplate, Database, History, Plus, Zap, Bot
} from 'lucide-react';
import WorkflowAutomation from '../components/WorkflowAutomation';
import TemplateGallery from '@/components/Automations/TemplateGallery';
import WorkflowTables from '@/components/Automations/WorkflowTables';
import FlowVersioning from '@/components/Automations/FlowVersioning';
import AgentWorkflowGenerator from '@/components/Automations/AgentWorkflowGenerator';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type TabType = 'flows' | 'agents' | 'templates' | 'tables' | 'versions';

const TABS = [
  { id: 'flows' as TabType, label: 'Flows', icon: Play, description: 'Build and manage your automations' },
  { id: 'agents' as TabType, label: 'AI Agents', icon: Bot, description: 'Specialty agents create workflows' },
  { id: 'templates' as TabType, label: 'Templates', icon: LayoutTemplate, description: 'Pre-built workflow templates' },
  { id: 'tables' as TabType, label: 'Tables', icon: Database, description: 'Data storage for workflows' },
  { id: 'versions' as TabType, label: 'Versions', icon: History, description: 'Version history' },
];

const AutomationsPage: React.FC = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('flows');

  const handleUseTemplate = (template: any) => {
    // Store template and switch to flows tab
    sessionStorage.setItem('selectedTemplate', JSON.stringify(template));
    setActiveTab('flows');
  };

  return (
    <>
      <Head>
        <title>Automations | Atom</title>
        <meta name="description" content="Build powerful workflow automations with AI. Connect your apps and automate tasks." />
      </Head>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Header with Tabs */}
        <div className="bg-white border-b sticky top-0 z-20">
          <div className="max-w-screen-2xl mx-auto px-4">
            <div className="flex items-center justify-between py-4">
              <div className="flex items-center gap-3">
                <div className="bg-violet-600 p-2 rounded-lg">
                  <Zap className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Automations</h1>
                  <p className="text-sm text-gray-500">Build workflows with AI • 30+ integrations</p>
                </div>
              </div>
              <Button onClick={() => setActiveTab('flows')}>
                <Plus className="w-4 h-4 mr-2" />
                New Automation
              </Button>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-3 border-b-2 transition-colors font-medium text-sm",
                      activeTab === tab.id
                        ? "border-violet-600 text-violet-600"
                        : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1">
          {activeTab === 'flows' && (
            <WorkflowAutomation />
          )}

          {activeTab === 'agents' && (
            <AgentWorkflowGenerator
              onWorkflowGenerated={(wf) => console.log('Generated:', wf)}
              onDeployWorkflow={(wf) => {
                console.log('Deploying:', wf);
                setActiveTab('flows');
              }}
              className="h-[calc(100vh-120px)]"
            />
          )}

          {activeTab === 'templates' && (
            <TemplateGallery onUseTemplate={handleUseTemplate} />
          )}

          {activeTab === 'tables' && (
            <WorkflowTables className="h-[calc(100vh-120px)]" />
          )}

          {activeTab === 'versions' && (
            <FlowVersioning className="h-[calc(100vh-120px)]" />
          )}
        </div>
      </div>
    </>
  );
};

export default AutomationsPage;
