import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { queryNotionTasks } from '../../../../project/functions/atom-agent/skills/notionAndResearchSkills';
import { getRepoCommitActivity } from '../../../../project/functions/atom-agent/skills/githubSkills';
import { searchMySlackMessages } from '../../../../project/functions/atom-agent/skills/slackSkills';
import { getMeetingLoad } from '../../../../project/functions/atom-agent/skills/calendarSkills';
import { analyzeSentiment } from '../../../../desktop/tauri/src/lib/sentiment';
import { NotionTask } from '../../../../project/functions/types';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  const userId = session.getUserId();
  const {
    notionApiKey,
    notionDatabaseId,
    githubOwner,
    githubRepo,
    slackChannelId,
  } = req.body;

  if (
    !notionApiKey ||
    !notionDatabaseId ||
    !githubOwner ||
    !githubRepo ||
    !slackChannelId
  ) {
    return res
      .status(400)
      .json({ message: 'Notion, GitHub, and Slack credentials are required' });
  }

  try {
    // Notion Task Score
    const tasksResponse = await queryNotionTasks(
      userId,
      { database_id: notionDatabaseId },
      notionApiKey
    );
    let notionScore = 0;
    if (tasksResponse.ok && tasksResponse.data) {
      const tasks: NotionTask[] = tasksResponse.data.tasks;
      if (tasks.length > 0) {
        const completedTasks = tasks.filter(
          (task) => task.status === 'Done'
        ).length;
        notionScore = Math.round((completedTasks / tasks.length) * 100);
      } else {
        notionScore = 100;
      }
    }

    // GitHub Score
    const commitActivity = await getRepoCommitActivity(
      userId,
      githubOwner,
      githubRepo
    );
    const pullRequests = await getRepoPullRequestActivity(
      userId,
      githubOwner,
      githubRepo
    );
    let githubScore = 0;
    if (commitActivity && pullRequests) {
      const commitScore =
        commitActivity.slice(-10).filter((week: any) => week.total > 0).length *
        5;
      const openPRs = pullRequests.filter(
        (pr: any) => pr.state === 'open'
      ).length;
      const prScore = Math.max(0, 50 - openPRs * 10);
      githubScore = commitScore + prScore;
    }

    // Slack Sentiment Score
    const messages = await searchMySlackMessages(
      userId,
      `in:${slackChannelId}`,
      100
    );
    let sentimentScore = 50; // Default to neutral
    if (messages.length > 0) {
      const totalScore = messages.reduce(
        (acc, msg) => acc + analyzeSentiment(msg.text),
        0
      );
      sentimentScore = Math.round((totalScore / messages.length) * 10 + 50);
    }

    // Google Calendar Meeting Load Score
    const timeMin = new Date();
    timeMin.setDate(timeMin.getDate() - 7);
    const timeMax = new Date();
    const events = await getMeetingLoad(
      userId,
      timeMin.toISOString(),
      timeMax.toISOString()
    );
    let meetingLoadScore = 100;
    if (events) {
      const totalMeetingHours = events.reduce((acc: number, event: any) => {
        const start = new Date(event.start.dateTime);
        const end = new Date(event.end.dateTime);
        return acc + (end.getTime() - start.getTime()) / 1000 / 60 / 60;
      }, 0);
      // Inverse score: more hours = lower score
      meetingLoadScore = Math.max(0, 100 - Math.round(totalMeetingHours * 5));
    }

    // Combine scores
    const score = Math.round(
      (notionScore + githubScore + sentimentScore + meetingLoadScore) / 4
    );

    return res.status(200).json({ score });
  } catch (error) {
    console.error('Error calculating project health score:', error);
    return res
      .status(500)
      .json({ message: 'Failed to calculate project health score' });
  }
}
