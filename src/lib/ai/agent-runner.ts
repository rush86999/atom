import { DatabaseService, getDatabase } from '../database';
import { v4 as uuidv4 } from 'uuid';
import { LLMRouter } from './llm-router';
import { AgentGovernanceService } from './agent-governance';
import { AgentExperience, WorldModelService } from './world-model';
import { PlanningService } from './planning-service';
import { LearningAdaptationEngine } from './learning-adaptation-engine';

import { SkillRegistryService } from './skill-registry';
import { SkillExecutorService } from './skill-executor';
import { getDynamicSkillBuilder } from './dynamic-skill-tools';

interface AgentExecutionResult {
    executionId: string;
    status: 'completed' | 'failed';
    output: string;
    steps: any[];
}

export class AgentRunner {
    private db: DatabaseService;
    private llm: LLMRouter;
    private governance: AgentGovernanceService;
    private worldModel: WorldModelService;
    private planner: PlanningService;
    private learning: LearningAdaptationEngine;
    private skillRegistry: SkillRegistryService;
    private skillExecutor: SkillExecutorService;

    constructor(db: DatabaseService) {
        this.db = db;
        this.llm = new LLMRouter(db);
        this.governance = new AgentGovernanceService(db);
        this.worldModel = new WorldModelService(db);
        this.planner = new PlanningService(db);
        this.learning = new LearningAdaptationEngine(db);
        this.skillRegistry = new SkillRegistryService();
        this.skillExecutor = new SkillExecutorService();
    }

    public getLearningEngine(): LearningAdaptationEngine {
        return this.learning;
    }

    /**
     * Run an agent task with persistent tracing
     */
    async runAgent(
        workspaceId: string,
        agentId: string,
        task: string,
        input: any,
        triggeredBy: 'manual' | 'schedule' | 'api' = 'manual'
    ): Promise<AgentExecutionResult> {
        // 1. Create Execution Record
        const executionId = uuidv4();
        await this.db.query(`
            INSERT INTO agent_executions (
                id, agent_id, workspace_id, status, input_summary, triggered_by, started_at
            ) VALUES ($1, $2, $3, 'running', $4, $5, NOW())
        `, [executionId, agentId, workspaceId, JSON.stringify(input), triggeredBy]);

        const steps: any[] = [];
        let finalOutput = '';
        let status: 'completed' | 'failed' = 'failed';

        try {
            // 2. Fetch or Create Persistent Plan
            let taskList = await this.planner.getActiveTaskList(agentId, workspaceId);
            if (!taskList) {
                // Determine if this is a new high-level objective
                taskList = await this.planner.createTaskList(agentId, workspaceId, task);
                // For MVP, treat the input 'task' as the first step
                const newTask = await this.planner.addTask(taskList.id, task, 'high');
                taskList.tasks.push(newTask);
            }

            // 3. Get Pending Tasks
            // In a real loop, we would iterate. Here we pick the next pending one.
            const pendingTasks = taskList.tasks.filter(t => t.status === 'pending');
            const currentTask = pendingTasks.length > 0 ? pendingTasks[0] : null;

            // Update task status to in_progress
            if (currentTask) {
                await this.planner.updateTaskStatus(currentTask.id, 'in_progress');
            }

            // 4. Fetch Context from Learning Engine (LanceDB - Long Term)
            let experiences: any[] = [];
            try {
                const embedding = await this.llm.getEmbedding(workspaceId, task);
                experiences = await this.learning.findRelevantExperiences(workspaceId, embedding, 3);
            } catch (err) {
                console.warn('[AgentRunner] Failed to retrieve LanceDB experiences:', err);
            }
            const longTermContext = experiences.map(e => `[Experience ${e.type}] ${JSON.stringify(e.outcomes)}`).join('\n');

            // 4b. Fetch Recent History from Postgres (Short Term)
            const recentHistory = await this.getHistory(agentId, 5);
            const shortTermContext = recentHistory.map(h =>
                `[Recent Execution ${h.status}] Input: ${h.input_summary} Result: ${h.result_summary || 'N/A'}`
            ).join('\n');

            // 4c. Fetch Dynamic Skills
            const agentSkills = await this.skillRegistry.getAgentSkills(agentId);
            const toolsContext = agentSkills.map(s => {
                return `- ${s.skill.name} (${s.skill.type}): ${s.skill.description || ''} Input Schema: ${JSON.stringify(s.skill.inputSchema)}`;
            }).join('\n');

            // 4d. Add System Tools
            const systemToolsContext = `
- register_script_skill (system): Create a new Node.js script tool. Args: { name, description, code, inputSchema, outputSchema }
- register_api_skill (system): Create a new REST API tool. Args: { name, description, url, method, headers, inputSchema, outputSchema }
- register_container_skill (system): Create a cloud-based container tool (Fly.io). Use this for SaaS/Cloud tasks.
- register_docker_skill (system): Create a local Docker-based tool. Use this ONLY for local Desktop/Tauri tasks.
            `;

            const isCloud = !!workspaceId && process.env.NODE_ENV === 'production';
            const environmentNote = isCloud
                ? "ENVIRONMENT: SaaS/Cloud (Fly.io). Prefer 'register_container_skill' for containerized tasks."
                : "ENVIRONMENT: Desktop/Local. Prefer 'register_docker_skill' for local containerized tasks.";

            // Build Context Prompt
            const contextPrompt = `
Task: ${currentTask ? currentTask.description : task}
Input: ${JSON.stringify(input)}

Active Plan:
${taskList.tasks.map(t => `- [${t.status}] ${t.description}`).join('\n')}

Recent Activity (Short Term Memory):
${shortTermContext}

Relevant Learnings (Long Term Memory):
${longTermContext}

Available Tools:
${toolsContext}

System Skills:
${systemToolsContext}

${environmentNote}

You are an autonomous agent. Reason step-by-step.
If you identify a missing capability required to complete the task, use "register_script_skill", "register_api_skill", "register_docker_skill", or "register_container_skill" based on the environment above.
For each step, output a JSON object:
{
  "thought": "analysis of situation",
  "action": { "tool": "tool_name", "args": {...} } OR null if done
  "final_answer": "answer" if done
}
            `;

            // 5. Execution Loop (Simplified 1-shot)
            const response = await this.llm.call(workspaceId, {
                model: 'gpt-4o',
                type: 'agent_execution',
                messages: [
                    { role: 'system', content: 'You are a precise agent. Generate a trace of your execution.' },
                    { role: 'user', content: contextPrompt }
                ]
            }) as { content: string; model: string; provider: string };

            // Parse result (reuse existing logic)
            let parsedSteps = [];
            try {
                const cleanJson = response.content.replace(/```json|```/g, '').trim();
                if (cleanJson.startsWith('[')) {
                    parsedSteps = JSON.parse(cleanJson);
                } else {
                    parsedSteps = [JSON.parse(cleanJson)];
                }
            } catch (e) {
                parsedSteps = [{
                    thought: "Processing request...",
                    action: null,
                    observation: "Processed via LLM",
                    final_answer: response.content
                }];
            }

            // 6. Record Trace Steps
            let stepNum = 1;
            for (const step of parsedSteps) {
                // Governance Check
                if (step.action) {
                    const govCheck = await this.governance.canPerformAction(workspaceId, agentId, step.action.tool);
                    if (!govCheck.allowed) {
                        step.observation = `Error: Action blocked. ${govCheck.reason}`;
                        step.status = 'error';
                    } else {
                        // Check if it matches a dynamic skill
                        const matchedSkill = agentSkills.find(s => s.skill.name === step.action.tool);

                        if (matchedSkill) {
                            try {
                                const result = await this.skillExecutor.executeSkill(
                                    matchedSkill.skill,
                                    step.action.args,
                                    agentId,
                                    workspaceId,
                                    matchedSkill.configOverrides
                                );
                                step.observation = JSON.stringify(result.result);
                            } catch (skillErr: any) {
                                step.observation = `Error executing skill: ${skillErr.message}`;
                                step.status = 'error';
                            }
                        } else if (['register_script_skill', 'register_api_skill', 'register_container_skill', 'register_docker_skill'].includes(step.action.tool)) {
                            // Handle System Tools for Dynamic Creation
                            try {
                                const builder = getDynamicSkillBuilder();
                                let skill;
                                if (step.action.tool === 'register_script_skill') {
                                    skill = await builder.registerScriptSkill(workspaceId!, agentId, step.action.args as any);
                                } else if (step.action.tool === 'register_api_skill') {
                                    skill = await builder.registerApiSkill(workspaceId!, agentId, step.action.args as any);
                                } else if (step.action.tool === 'register_container_skill') {
                                    skill = await builder.registerContainerSkill(workspaceId!, agentId, step.action.args as any);
                                } else {
                                    skill = await builder.registerDockerSkill(workspaceId!, agentId, step.action.args as any);
                                }
                                step.observation = `Successfully registered and assigned new skill: ${skill.name} (${skill.id}). Type: ${skill.type}`;

                                // Refresh agentSkills for subsequent steps in this execution
                                agentSkills.push({
                                    agentId,
                                    skillId: skill.id,
                                    enabled: true,
                                    configOverrides: null,
                                    skill
                                });
                            } catch (buildErr: any) {
                                step.observation = `Error registering skill: ${buildErr.message}`;
                                step.status = 'error';
                            }
                        } else {
                            step.observation = "Action executed successfully (Simulated)";
                        }
                    }
                }

                await this.db.query(`
                    INSERT INTO agent_trace_steps (
                        execution_id, step_number, thought, action, observation, final_answer, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                `, [
                    executionId, stepNum, step.thought || '', JSON.stringify(step.action),
                    step.observation || '', step.final_answer || null
                ]);

                steps.push({ ...step, step: stepNum });
                if (step.final_answer) finalOutput = step.final_answer;
                stepNum++;
            }

            status = 'completed';

            // 7. Update Task Status & Record Experience
            if (currentTask) {
                await this.planner.updateTaskStatus(currentTask.id, 'completed');

                // Record Experience
                // Generate embedding for the experience context (Task description + Outcome)
                let experienceVector: number[] | undefined;
                try {
                    experienceVector = await this.llm.getEmbedding(workspaceId, `${currentTask.description} Outcome: ${status}`);
                } catch (e) { /* ignore */ }

                await this.learning.recordExperience(workspaceId, {
                    type: status === 'completed' ? 'success' : 'failure',
                    context: {
                        environment: 'production',
                        agentId: agentId,
                        taskId: currentTask.id,
                        conditions: { triggeredBy }
                    },
                    inputs: input || {},
                    actions: steps.map(s => ({
                        type: s.action?.tool || 'reasoning',
                        parameters: s.action?.args || {},
                        timestamp: new Date()
                    })),
                    outcomes: {
                        primary: status === 'completed' ? 1 : 0,
                        secondary: {},
                        duration: 0,
                        quality: 1.0,
                        efficiency: 1.0
                    },
                    feedback: {
                        immediate: 1,
                        source: 'system_execution',
                        confidence: 1.0
                    },
                    reflections: [],
                    patterns: [],
                    vector: experienceVector
                });
            }

            // 8. Update Execution Status
            // 3. Update execution record on success
            await this.db.query(
                `UPDATE agent_executions 
                 SET status = 'completed', output_summary = $1, completed_at = NOW()
                 WHERE id = $2 AND workspace_id = $3`,
                [finalOutput, executionId, workspaceId]
            );

            // 9. Account for Storage (HOT Trace)
            const traceSize = Buffer.byteLength(JSON.stringify(input)) +
                Buffer.byteLength(finalOutput) +
                Buffer.byteLength(JSON.stringify(steps));

            await this.db.updateStorageUsage(workspaceId, traceSize, 'agent_trace');

        } catch (error: any) {
            console.error('AgentRunner Error:', error);
            status = 'failed';
            // 4. Update execution record on error
            await this.db.query(
                `UPDATE agent_executions 
                 SET status = 'failed', error_message = $1, completed_at = NOW()
                 WHERE id = $2 AND workspace_id = $3`,
                [error.message, executionId, workspaceId]
            );
        }

        return {
            executionId,
            status,
            output: finalOutput,
            steps
        };
    }

    /**
     * Get execution history for an agent
     */
    async getHistory(agentId: string, limit = 20): Promise<any[]> {
        const res = await this.db.query(`
            SELECT * FROM agent_executions 
            WHERE agent_id = $1 
            ORDER BY started_at DESC 
            LIMIT $2
        `, [agentId, limit]);
        return res.rows;
    }

    /**
     * Get full trace for an execution
     */
    async getTrace(executionId: string): Promise<any[]> {
        const res = await this.db.query(`
            SELECT * FROM agent_trace_steps 
            WHERE execution_id = $1 
            ORDER BY step_number ASC
        `, [executionId]);
        return res.rows;
    }
}

// Singleton
let agentRunner: AgentRunner | null = null;
export function getAgentRunner(): AgentRunner {
    if (!agentRunner) {
        agentRunner = new AgentRunner(getDatabase());
    }
    return agentRunner;
}
