import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";
// TODO: Zoom OAuth implementation pending dependencies
// import { executeGraphQLQuery } from '../../../../../project/functions/_libs/graphqlClient';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  return res.status(501).json({ message: "Zoom OAuth temporarily disabled" });
}
