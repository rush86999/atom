import { NextApiRequest, NextApiResponse } from "next";
import { getSession } from "supertokens-node/nextjs";
import { SessionContainer } from "supertokens-node/recipe/session";
// TODO: Zoom OAuth implementation pending dependencies
// import { executeGraphQLQuery } from '../../../../../project/functions/_libs/graphqlClient';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  return res.status(501).json({ message: "Zoom OAuth temporarily disabled" });
}
