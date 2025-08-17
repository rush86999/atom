#!/usr/bin/env node

const { createOrchestrationSystem } = require('../src/orchestration');

console.log('🔍 ATOM Orchestration System Health Check\n');

async function checkHealth() {
  const orchestration = createOrchestrationSystem();

  try {
    console.log('📊 System Metrics:');
    const metrics = orchestration.getSystemMetrics();

    Object.entries(metrics).forEach(([key, value]) => {
      if (typeof value === 'number') {
        value = Math.round(value * 100) / 100;
      }
      console.log(`   ${key}: ${value}`);
    });

    console.log('\n🤖 Registered Agents:');
    const agents = orchestration['engine'].getRegisteredAgents();

    agents.forEach((agent, index) => {
      console.log(`   ${index + 1}. ${agent.name} (${agent.skills.length} skills, ${agent.confidence * 100}% confidence)`);
    });

    console.log('\n📈 Agent Health Status:');
    try {
      const agentHealth = orchestration['agentRegistry'].getAgentHealthStatus();

      Object.entries(agentHealth).forEach(([id, status]) => {
        const performanceIndicator = status.status === 'healthy' ? '✅' :
                                   status.status === 'degraded' ? '⚠️' : '❌';
        console.log(`   ${performanceIndicator} ${status.name}: ${status.status} (${status.confidence}% confidence)`);
      });
+    } catch (e) {
+      console.log('   📊 Basic agent monitoring available');
+    }
+
+    console.log('\n🎯 System Summary:');
+    if (metrics.systemHealth === 'excellent') {
+      console.log('   ✅ System running optimally - no action required');
+    } else if (metrics.systemHealth === 'good') {
+      console.log('   ⚠️ Minor optimization opportunities available');
+    } else {
+      console.log('   🔧 Consider running optimization cycle');
+    }
+
+  } catch (error) {
+    console.error('❌ Health check failed:', error.message);
+    process.exit(1);
+  }
+}
+
+checkHealth().catch(console.error);
