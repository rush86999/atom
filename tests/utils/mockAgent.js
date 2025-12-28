// /home/developer/projects/atom/atom/atomic-docker/app_build_docker/tests/utils/mockAgent.js
export const mockAgentResponse = {
  id: 'agent-123',
  status: 'completed',
  result: {
    message: 'Task completed successfully',
    data: { /* your agent response structure */ }
  }
};

export const mockAgentError = {
  error: 'Agent execution failed',
  details: 'Invalid input parameters'
};