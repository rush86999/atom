import { SkillMessageHistoryType } from '@chat/_libs/types/Messaging/MessagingTypes';

export type ChatBrainBodyType = {
  chat: SkillMessageHistoryType;
  userId: string;
  timezone: string;
  active?: boolean;
  id: string;
};

export type OneToManyActionsType = { actions: string[] };
