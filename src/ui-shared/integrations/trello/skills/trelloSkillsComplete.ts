/**
 * Complete Trello Project Management Skills
 * All Trello project management operations
 */

import axios, { AxiosResponse } from 'axios';
import { logger } from '@/utils/logging';

// Interfaces for Trello data
interface TrelloBoard {
  id: string;
  name: string;
  description: string;
  closed: boolean;
  url: string;
  shortUrl: string;
  shortLink: string;
  dateLastActivity: string;
  pinned: boolean;
  starred: boolean;
  subscribed: boolean;
  totalCards: number;
  totalLists: number;
  totalMembers: number;
  totalChecklists: number;
}

interface TrelloCard {
  id: string;
  idBoard: string;
  idList: string;
  name: string;
  description: string;
  closed: boolean;
  due?: string;
  dueComplete: boolean;
  start?: string;
  url: string;
  shortUrl: string;
  shortLink: string;
  subscribed: boolean;
  labels: Array<{ id: string; name: string; color: string }>;
  members: Array<{ id: string; username: string; fullName: string }>;
  checklists: Array<{ id: string; name: string; checkItems: Array<{ state: string; name: string }> }>;
  badges: {
    comments: number;
    attachments: number;
    checkItems: number;
    checkItemsChecked: number;
  };
  dateLastActivity: string;
}

interface TrelloList {
  id: string;
  name: string;
  closed: boolean;
  pos: number;
  subscribed: boolean;
  totalCards: number;
  cards?: TrelloCard[];
}

interface TrelloMember {
  id: string;
  username: string;
  fullName: string;
  email: string;
  avatarUrl: string;
  bio: string;
  status: string;
  memberType: string;
  confirmed: boolean;
  activityBlocked: boolean;
  loginAllowed: boolean;
}

interface TrelloMemorySettings {
  userId: string;
  ingestionEnabled: boolean;
  syncFrequency: string;
  dataRetentionDays: number;
  includeBoards: string[];
  excludeBoards: string[];
  includeArchivedBoards: boolean;
  includeCards: boolean;
  includeLists: boolean;
  includeMembers: boolean;
  includeChecklists: boolean;
  includeLabels: boolean;
  includeAttachments: boolean;
  includeActivities: boolean;
  maxCardsPerSync: number;
  maxActivitiesPerSync: number;
  syncArchivedCards: boolean;
  syncCardAttachments: boolean;
  indexCardContent: boolean;
  searchEnabled: boolean;
  semanticSearchEnabled: boolean;
  metadataExtractionEnabled: boolean;
  boardTrackingEnabled: boolean;
  memberAnalysisEnabled: boolean;
  lastSyncTimestamp?: string;
  nextSyncTimestamp?: string;
  syncInProgress: boolean;
  errorMessage?: string;
  createdAt?: string;
  updatedAt?: string;
}

// Atom API client
const atomApiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Utility functions
const trelloUtils = {
  validateBoardId: (boardId: string): boolean => {
    return boardId && boardId.length >= 8 && boardId.length <= 64;
  },

  validateCardId: (cardId: string): boolean => {
    return cardId && cardId.length >= 8 && cardId.length <= 64;
  },

  validateListId: (listId: string): boolean => {
    return listId && listId.length >= 8 && listId.length <= 64;
  },

  validateMemberId: (memberId: string): boolean => {
    return memberId && memberId.length >= 8 && memberId.length <= 64;
  },

  validateApiKey: (apiKey: string): boolean => {
    return apiKey && apiKey.length >= 16 && apiKey.length <= 128;
  },

  validateOAuthToken: (oauthToken: string): boolean => {
    return oauthToken && oauthToken.length >= 16 && oauthToken.length <= 256;
  },

  createBoard: (data: any): TrelloBoard => {
    return {
      id: data.id || '',
      name: data.name || '',
      description: data.desc || '',
      closed: data.closed || false,
      url: data.url || '',
      shortUrl: data.shortUrl || '',
      shortLink: data.shortLink || '',
      dateLastActivity: data.dateLastActivity || '',
      pinned: data.pinned || false,
      starred: data.starred || false,
      subscribed: data.subscribed || false,
      totalCards: data.totalCards || 0,
      totalLists: data.totalLists || 0,
      totalMembers: data.totalMembers || 0,
      totalChecklists: data.totalChecklists || 0
    };
  },

  createCard: (data: any): TrelloCard => {
    return {
      id: data.id || '',
      idBoard: data.idBoard || '',
      idList: data.idList || '',
      name: data.name || '',
      description: data.desc || '',
      closed: data.closed || false,
      due: data.due || '',
      dueComplete: data.dueComplete || false,
      start: data.start || '',
      url: data.url || '',
      shortUrl: data.shortUrl || '',
      shortLink: data.shortLink || '',
      subscribed: data.subscribed || false,
      labels: data.labels || [],
      members: data.members || [],
      checklists: data.checklists || [],
      badges: data.badges || {
        comments: 0,
        attachments: 0,
        checkItems: 0,
        checkItemsChecked: 0
      },
      dateLastActivity: data.dateLastActivity || ''
    };
  },

  createList: (data: any): TrelloList => {
    return {
      id: data.id || '',
      name: data.name || '',
      closed: data.closed || false,
      pos: data.pos || 0,
      subscribed: data.subscribed || false,
      totalCards: data.totalCards || 0,
      cards: data.cards || []
    };
  },

  createMember: (data: any): TrelloMember => {
    return {
      id: data.id || '',
      username: data.username || '',
      fullName: data.fullName || '',
      email: data.email || '',
      avatarUrl: data.avatarUrl || '',
      bio: data.bio || '',
      status: data.status || '',
      memberType: data.memberType || '',
      confirmed: data.confirmed || false,
      activityBlocked: data.activityBlocked || false,
      loginAllowed: data.loginAllowed || false
    };
  },

  validateSearchQuery: (query: string): boolean => {
    if (!query) return false;
    if (query.length > 1000) return false;
    // Check for potentially dangerous characters
    const dangerousChars = /[<>]/;
    return !dangerousChars.test(query);
  },

  validateSyncFrequency: (frequency: string): boolean => {
    const validFrequencies = ['real-time', 'hourly', 'daily', 'weekly', 'manual'];
    return validFrequencies.includes(frequency);
  }
};

// Complete Trello skills
const trelloSkills = {

  /**
   * Get Trello boards
   */
  trelloGetBoards: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    filter: string = 'all'
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello boards for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/boards/list', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        filter: filter
      });
      
      const data = response.data;
      
      if (data.ok) {
        const boards = data.boards.map((board: any) => trelloUtils.createBoard(board));
        logger.info(`Trello boards retrieved: ${boards.length} boards`);
        return {
          success: true,
          boards: boards
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello boards');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetBoards:', error);
      throw new Error(`Failed to get Trello boards: ${error.message}`);
    }
  },

  /**
   * Get Trello board details
   */
  trelloGetBoard: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardId: string,
    includeLists: boolean = true,
    includeCards: boolean = true,
    includeMembers: boolean = true
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello board details for user ${userId}: ${boardId}`);
      
      if (!trelloUtils.validateBoardId(boardId)) {
        throw new Error('Invalid board ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/boards/get', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_id: boardId,
        include_lists: includeLists,
        include_cards: includeCards,
        include_members: includeMembers
      });
      
      const data = response.data;
      
      if (data.ok) {
        const board = trelloUtils.createBoard(data.board);
        logger.info(`Trello board details retrieved: ${boardId}`);
        return {
          success: true,
          board: board
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello board');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetBoard:', error);
      throw new Error(`Failed to get Trello board: ${error.message}`);
    }
  },

  /**
   * Get Trello cards
   */
  trelloGetCards: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardId: string,
    listId: string = null,
    filter: string = 'all'
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello cards for user ${userId}: ${boardId}`);
      
      if (!trelloUtils.validateBoardId(boardId) && !trelloUtils.validateListId(listId)) {
        throw new Error('Invalid board ID or list ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/cards/list', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_id: boardId,
        list_id: listId,
        filter: filter
      });
      
      const data = response.data;
      
      if (data.ok) {
        const cards = data.cards.map((card: any) => trelloUtils.createCard(card));
        logger.info(`Trello cards retrieved: ${cards.length} cards`);
        return {
          success: true,
          cards: cards
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello cards');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetCards:', error);
      throw new Error(`Failed to get Trello cards: ${error.message}`);
    }
  },

  /**
   * Get Trello card details
   */
  trelloGetCard: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    cardId: string,
    includeAttachments: boolean = true,
    includeChecklists: boolean = true,
    includeMembers: boolean = true
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello card details for user ${userId}: ${cardId}`);
      
      if (!trelloUtils.validateCardId(cardId)) {
        throw new Error('Invalid card ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/cards/get', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        card_id: cardId,
        include_attachments: includeAttachments,
        include_checklists: includeChecklists,
        include_members: includeMembers
      });
      
      const data = response.data;
      
      if (data.ok) {
        const card = trelloUtils.createCard(data.card);
        logger.info(`Trello card details retrieved: ${cardId}`);
        return {
          success: true,
          card: card
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello card');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetCard:', error);
      throw new Error(`Failed to get Trello card: ${error.message}`);
    }
  },

  /**
   * Create Trello card
   */
  trelloCreateCard: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    name: string,
    idList: string,
    desc: string = '',
    due: string = '',
    idMembers: string[] = [],
    idLabels: string[] = []
  ): Promise<any> => {
    try {
      logger.info(`Creating Trello card for user ${userId}: ${name}`);
      
      if (!trelloUtils.validateListId(idList)) {
        throw new Error('Invalid list ID');
      }
      
      if (!name || name.trim() === '') {
        throw new Error('Card name is required');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/cards/create', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        name: name,
        id_list: idList,
        description: desc,
        due: due,
        id_members: idMembers,
        id_labels: idLabels
      });
      
      const data = response.data;
      
      if (data.ok) {
        const card = trelloUtils.createCard(data.card);
        logger.info(`Trello card created: ${card.id}`);
        return {
          success: true,
          card: card
        };
      } else {
        throw new Error(data.error || 'Failed to create Trello card');
      }
    } catch (error: any) {
      logger.error('Error in trelloCreateCard:', error);
      throw new Error(`Failed to create Trello card: ${error.message}`);
    }
  },

  /**
   * Update Trello card
   */
  trelloUpdateCard: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    cardId: string,
    name: string = null,
    desc: string = null,
    due: string = null,
    closed: boolean = null,
    pos: string = null,
    dueComplete: boolean = null,
    idMembers: string[] = null,
    idLabels: string[] = null
  ): Promise<any> => {
    try {
      logger.info(`Updating Trello card for user ${userId}: ${cardId}`);
      
      if (!trelloUtils.validateCardId(cardId)) {
        throw new Error('Invalid card ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/cards/update', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        card_id: cardId,
        name: name,
        description: desc,
        due: due,
        closed: closed,
        pos: pos,
        due_complete: dueComplete,
        id_members: idMembers,
        id_labels: idLabels
      });
      
      const data = response.data;
      
      if (data.ok) {
        const card = trelloUtils.createCard(data.card);
        logger.info(`Trello card updated: ${cardId}`);
        return {
          success: true,
          card: card
        };
      } else {
        throw new Error(data.error || 'Failed to update Trello card');
      }
    } catch (error: any) {
      logger.error('Error in trelloUpdateCard:', error);
      throw new Error(`Failed to update Trello card: ${error.message}`);
    }
  },

  /**
   * Delete Trello card
   */
  trelloDeleteCard: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    cardId: string
  ): Promise<boolean> => {
    try {
      logger.info(`Deleting Trello card for user ${userId}: ${cardId}`);
      
      if (!trelloUtils.validateCardId(cardId)) {
        throw new Error('Invalid card ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/cards/delete', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        card_id: cardId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello card deleted: ${cardId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Trello card');
      }
    } catch (error: any) {
      logger.error('Error in trelloDeleteCard:', error);
      throw new Error(`Failed to delete Trello card: ${error.message}`);
    }
  },

  /**
   * Get Trello lists
   */
  trelloGetLists: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardId: string,
    includeCards: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello lists for user ${userId}: ${boardId}`);
      
      if (!trelloUtils.validateBoardId(boardId)) {
        throw new Error('Invalid board ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/lists/get', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_id: boardId,
        include_cards: includeCards
      });
      
      const data = response.data;
      
      if (data.ok) {
        const lists = data.lists.map((list: any) => trelloUtils.createList(list));
        logger.info(`Trello lists retrieved: ${lists.length} lists`);
        return {
          success: true,
          lists: lists
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello lists');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetLists:', error);
      throw new Error(`Failed to get Trello lists: ${error.message}`);
    }
  },

  /**
   * Get Trello members
   */
  trelloGetMembers: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardId: string = null,
    includeBoards: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello members for user ${userId}: ${boardId || 'all'}`);
      
      if (boardId && !trelloUtils.validateBoardId(boardId)) {
        throw new Error('Invalid board ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/members/list', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_id: boardId,
        include_boards: includeBoards
      });
      
      const data = response.data;
      
      if (data.ok) {
        const members = data.members.map((member: any) => trelloUtils.createMember(member));
        logger.info(`Trello members retrieved: ${members.length} members`);
        return {
          success: true,
          members: members
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello members');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetMembers:', error);
      throw new Error(`Failed to get Trello members: ${error.message}`);
    }
  },

  /**
   * Create Trello checklist
   */
  trelloCreateChecklist: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    name: string,
    idCard: string,
    checkItems: string[] = []
  ): Promise<any> => {
    try {
      logger.info(`Creating Trello checklist for user ${userId}: ${name}`);
      
      if (!trelloUtils.validateCardId(idCard)) {
        throw new Error('Invalid card ID');
      }
      
      if (!name || name.trim() === '') {
        throw new Error('Checklist name is required');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/checklists/create', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        name: name,
        id_card: idCard,
        check_items: checkItems
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello checklist created: ${data.checklist.id}`);
        return {
          success: true,
          checklist: data.checklist
        };
      } else {
        throw new Error(data.error || 'Failed to create Trello checklist');
      }
    } catch (error: any) {
      logger.error('Error in trelloCreateChecklist:', error);
      throw new Error(`Failed to create Trello checklist: ${error.message}`);
    }
  },

  /**
   * Create Trello label
   */
  trelloCreateLabel: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    name: string,
    color: string,
    idBoard: string
  ): Promise<any> => {
    try {
      logger.info(`Creating Trello label for user ${userId}: ${name}`);
      
      if (!trelloUtils.validateBoardId(idBoard)) {
        throw new Error('Invalid board ID');
      }
      
      if (!name || name.trim() === '') {
        throw new Error('Label name is required');
      }
      
      if (!color || color.trim() === '') {
        throw new Error('Label color is required');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/labels/create', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        name: name,
        color: color,
        id_board: idBoard
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello label created: ${data.label.id}`);
        return {
          success: true,
          label: data.label
        };
      } else {
        throw new Error(data.error || 'Failed to create Trello label');
      }
    } catch (error: any) {
      logger.error('Error in trelloCreateLabel:', error);
      throw new Error(`Failed to create Trello label: ${error.message}`);
    }
  },

  /**
   * Search Trello cards
   */
  trelloSearchCards: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    query: string = '',
    idBoards: string[] = [],
    idCards: string[] = [],
    idLabels: string[] = [],
    idMembers: string[] = [],
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Trello cards for user ${userId}: ${query}`);
      
      if (query && !trelloUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/search/cards', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        query: query,
        id_boards: idBoards,
        id_cards: idCards,
        id_labels: idLabels,
        id_members: idMembers,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        const cards = data.cards.map((card: any) => trelloUtils.createCard(card));
        logger.info(`Trello cards search completed: ${cards.length} results`);
        return {
          success: true,
          cards: cards,
          count: data.count,
          searchFilters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Trello cards');
      }
    } catch (error: any) {
      logger.error('Error in trelloSearchCards:', error);
      throw new Error(`Failed to search Trello cards: ${error.message}`);
    }
  },

  /**
   * Get Trello board activities
   */
  trelloGetBoardActivities: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardId: string,
    limit: number = 50,
    before: string = '',
    since: string = ''
  ): Promise<any> => {
    try {
      logger.info(`Getting Trello board activities for user ${userId}: ${boardId}`);
      
      if (!trelloUtils.validateBoardId(boardId)) {
        throw new Error('Invalid board ID');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/activities/board', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_id: boardId,
        limit: limit,
        before: before,
        since: since
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello board activities retrieved: ${data.count} activities`);
        return {
          success: true,
          activities: data.activities,
          count: data.count,
          filters: data.filters
        };
      } else {
        throw new Error(data.error || 'Failed to get Trello board activities');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetBoardActivities:', error);
      throw new Error(`Failed to get Trello board activities: ${error.message}`);
    }
  },

  /**
   * Get Trello memory settings
   */
  trelloGetMemorySettings: async (userId: string): Promise<TrelloMemorySettings> => {
    try {
      logger.info(`Getting Trello memory settings for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/settings', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello memory settings retrieved for user ${userId}`);
        return data.settings;
      } else {
        throw new Error(data.error || 'Failed to get Trello memory settings');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetMemorySettings:', error);
      throw new Error(`Failed to get Trello memory settings: ${error.message}`);
    }
  },

  /**
   * Update Trello memory settings
   */
  trelloUpdateMemorySettings: async (
    userId: string,
    settings: Partial<TrelloMemorySettings>
  ): Promise<boolean> => {
    try {
      logger.info(`Updating Trello memory settings for user ${userId}`);
      
      // Validate sync frequency
      if (settings.syncFrequency && !trelloUtils.validateSyncFrequency(settings.syncFrequency)) {
        throw new Error('Invalid sync frequency');
      }
      
      const response = await atomApiClient.put('/api/trello/project-workflow/memory/settings', {
        user_id: userId,
        ...settings
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello memory settings updated for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to update Trello memory settings');
      }
    } catch (error: any) {
      logger.error('Error in trelloUpdateMemorySettings:', error);
      throw new Error(`Failed to update Trello memory settings: ${error.message}`);
    }
  },

  /**
   * Start Trello ingestion
   */
  trelloStartIngestion: async (
    userId: string,
    apiKey: string,
    oauthToken: string,
    boardIds: string[] = [],
    forceSync: boolean = false
  ): Promise<any> => {
    try {
      logger.info(`Starting Trello ingestion for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/ingest', {
        user_id: userId,
        api_key: apiKey,
        oauth_token: oauthToken,
        board_ids: boardIds,
        force_sync: forceSync
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello ingestion started: ${data.ingestion_result.boards_ingested} boards`);
        return data.ingestion_result;
      } else {
        throw new Error(data.error || 'Failed to start Trello ingestion');
      }
    } catch (error: any) {
      logger.error('Error in trelloStartIngestion:', error);
      throw new Error(`Failed to start Trello ingestion: ${error.message}`);
    }
  },

  /**
   * Get Trello sync status
   */
  trelloGetSyncStatus: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting Trello sync status for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/status', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello sync status retrieved for user ${userId}`);
        return data.memory_status;
      } else {
        throw new Error(data.error || 'Failed to get Trello sync status');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetSyncStatus:', error);
      throw new Error(`Failed to get Trello sync status: ${error.message}`);
    }
  },

  /**
   * Search Trello memory boards
   */
  trelloSearchMemoryBoards: async (
    userId: string,
    query: string = '',
    closed: boolean = null,
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Trello memory boards for user ${userId}: ${query}`);
      
      if (query && !trelloUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/search/boards', {
        user_id: userId,
        query: query,
        closed: closed,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello memory boards search completed: ${data.count} results`);
        return {
          boards: data.boards,
          count: data.count,
          searchFilters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Trello memory boards');
      }
    } catch (error: any) {
      logger.error('Error in trelloSearchMemoryBoards:', error);
      throw new Error(`Failed to search Trello memory boards: ${error.message}`);
    }
  },

  /**
   * Search Trello memory cards
   */
  trelloSearchMemoryCards: async (
    userId: string,
    query: string = '',
    boardId: string = null,
    listId: string = null,
    memberId: string = null,
    labelName: string = null,
    closed: boolean = null,
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Trello memory cards for user ${userId}: ${query}`);
      
      if (query && !trelloUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/search/cards', {
        user_id: userId,
        query: query,
        board_id: boardId,
        list_id: listId,
        member_id: memberId,
        label_name: labelName,
        closed: closed,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello memory cards search completed: ${data.count} results`);
        return {
          cards: data.cards,
          count: data.count,
          searchFilters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Trello memory cards');
      }
    } catch (error: any) {
      logger.error('Error in trelloSearchMemoryCards:', error);
      throw new Error(`Failed to search Trello memory cards: ${error.message}`);
    }
  },

  /**
   * Search Trello memory members
   */
  trelloSearchMemoryMembers: async (
    userId: string,
    query: string = '',
    limit: number = 50
  ): Promise<any> => {
    try {
      logger.info(`Searching Trello memory members for user ${userId}: ${query}`);
      
      if (query && !trelloUtils.validateSearchQuery(query)) {
        throw new Error('Invalid search query');
      }
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/search/members', {
        user_id: userId,
        query: query,
        limit: limit
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello memory members search completed: ${data.count} results`);
        return {
          members: data.members,
          count: data.count,
          searchFilters: data.search_filters
        };
      } else {
        throw new Error(data.error || 'Failed to search Trello memory members');
      }
    } catch (error: any) {
      logger.error('Error in trelloSearchMemoryMembers:', error);
      throw new Error(`Failed to search Trello memory members: ${error.message}`);
    }
  },

  /**
   * Get Trello ingestion statistics
   */
  trelloGetIngestionStats: async (userId: string): Promise<any> => {
    try {
      logger.info(`Getting Trello ingestion stats for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/ingestion-stats', {
        user_id: userId
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello ingestion stats retrieved for user ${userId}`);
        return data.ingestion_stats;
      } else {
        throw new Error(data.error || 'Failed to get Trello ingestion stats');
      }
    } catch (error: any) {
      logger.error('Error in trelloGetIngestionStats:', error);
      throw new Error(`Failed to get Trello ingestion stats: ${error.message}`);
    }
  },

  /**
   * Delete Trello user data
   */
  trelloDeleteUserData: async (userId: string): Promise<boolean> => {
    try {
      logger.info(`Deleting Trello user data for user ${userId}`);
      
      const response = await atomApiClient.post('/api/trello/project-workflow/memory/delete', {
        user_id: userId,
        confirm: true
      });
      
      const data = response.data;
      
      if (data.ok) {
        logger.info(`Trello user data deleted for user ${userId}`);
        return true;
      } else {
        throw new Error(data.error || 'Failed to delete Trello user data');
      }
    } catch (error: any) {
      logger.error('Error in trelloDeleteUserData:', error);
      throw new Error(`Failed to delete Trello user data: ${error.message}`);
    }
  }
};

// Export default
export default trelloSkills;