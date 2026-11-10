import type { NextApiRequest, NextApiResponse } from 'next';
import { forwardBackendApi } from '../../../lib/backend-api-proxy';

function isSkillsCatalogue(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return false;
  const result = payload as { success?: unknown; data?: { skills?: unknown; total?: unknown } };
  const skills = result.data?.skills;
  return result.success === true && Array.isArray(skills) &&
    Number.isInteger(result.data?.total) && result.data?.total === skills.length &&
    skills.every(row => row && typeof row === 'object' && !Array.isArray(row) &&
      typeof row.skill_id === 'string' && row.skill_id.length > 0);
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  return forwardBackendApi(req, res, '/api/skills/list', ['GET'], { validateResponse: isSkillsCatalogue });
}
