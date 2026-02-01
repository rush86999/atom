/**
 * Enhanced Trello Integration Skills
 * Natural language commands for Trello operations following established pattern
 */

import { 
  TrelloBoard,
  TrelloList,
  TrelloCard,
  TrelloMember,
  TrelloChecklist,
  TrelloLabel,
  TrelloAttachment,
  TrelloComment,
  TrelloAction
} from '../types/trello-types';

export interface TrelloSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'trello';
}

export class EnhancedTrelloSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language Trello command
   */
  async executeCommand(command: string, context?: any): Promise<TrelloSkillResult> {
    const lowerCommand = command.toLowerCase().trim();

    try {
      // Board commands
      if (lowerCommand.includes('board')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listBoards(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchBoards(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createBoard(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('edit')) {
          return await this.updateBoard(lowerCommand, context);
        }
        if (lowerCommand.includes('delete') || lowerCommand.includes('close')) {
          return await this.deleteBoard(lowerCommand, context);
        }
      }

      // List commands
      if (lowerCommand.includes('list')) {
        if (lowerCommand.includes('list') && !lowerCommand.includes('board') && !lowerCommand.includes('card')) {
          if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
            return await this.listsLists(lowerCommand, context);
          }
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchLists(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createList(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('edit')) {
          return await this.updateList(lowerCommand, context);
        }
        if (lowerCommand.includes('delete') || lowerCommand.includes('archive')) {
          return await this.deleteList(lowerCommand, context);
        }
      }

      // Card commands
      if (lowerCommand.includes('card')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listCards(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchCards(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createCard(lowerCommand, context);
        }
        if (lowerCommand.includes('update') || lowerCommand.includes('edit')) {
          return await this.updateCard(lowerCommand, context);
        }
        if (lowerCommand.includes('delete') || lowerCommand.includes('archive')) {
          return await this.deleteCard(lowerCommand, context);
        }
        if (lowerCommand.includes('move')) {
          return await this.moveCard(lowerCommand, context);
        }
        if (lowerCommand.includes('assign')) {
          return await this.assignCard(lowerCommand, context);
        }
        if (lowerCommand.includes('label') || lowerCommand.includes('tag')) {
          return await this.labelCard(lowerCommand, context);
        }
        if (lowerCommand.includes('comment')) {
          return await this.commentCard(lowerCommand, context);
        }
      }

      // Checklist commands
      if (lowerCommand.includes('checklist') || lowerCommand.includes('todo')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listChecklists(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createChecklist(lowerCommand, context);
        }
        if (lowerCommand.includes('add') || lowerCommand.includes('check')) {
          return await this.addChecklistItem(lowerCommand, context);
        }
      }

      // Member commands
      if (lowerCommand.includes('member') || lowerCommand.includes('user')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listMembers(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchMembers(lowerCommand, context);
        }
        if (lowerCommand.includes('profile')) {
          return await this.getUserProfile(lowerCommand, context);
        }
        if (lowerCommand.includes('invite')) {
          return await this.inviteMember(lowerCommand, context);
        }
      }

      // Search commands
      if (lowerCommand.includes('search')) {
        return await this.globalSearch(lowerCommand, context);
      }

      // Content creation commands
      if (lowerCommand.includes('create') || lowerCommand.includes('add') || lowerCommand.includes('new')) {
        if (lowerCommand.includes('task') || lowerCommand.includes('todo')) {
          return await this.createTask(lowerCommand, context);
        }
        if (lowerCommand.includes('story') || lowerCommand.includes('feature')) {
          return await this.createStory(lowerCommand, context);
        }
        if (lowerCommand.includes('bug') || lowerCommand.includes('issue')) {
          return await this.createBug(lowerCommand, context);
        }
      }

      // Action commands
      if (lowerCommand.includes('activities') || lowerCommand.includes('history') || lowerCommand.includes('log')) {
        return await this.getActivities(lowerCommand, context);
      }

      // Default: Search across Trello
      return await this.globalSearch(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'trello'
      };
    }
  }

  /**
   * List boards
   */
  private async listBoards(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/boards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          include_closed: this.extractIncludeClosed(command),
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        const boards = data.boards;
        const summary = this.generateBoardsSummary(boards);
        
        return {
          success: true,
          data: {
            boards,
            summary,
            total: data.total_count
          },
          action: 'list_boards',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list boards',
        action: 'list_boards',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_boards',
        platform: 'trello'
      };
    }
  }

  /**
   * List lists
   */
  private async listsLists(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const boardId = this.extractBoardId(command, context);
      const filters = this.extractListFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/lists`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          board_id: boardId,
          include_closed: filters.includeClosed,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const lists = data.lists;
        const summary = this.generateListsSummary(lists);
        
        return {
          success: true,
          data: {
            lists,
            summary,
            total: data.total_count
          },
          action: 'list_lists',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list lists',
        action: 'list_lists',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_lists',
        platform: 'trello'
      };
    }
  }

  /**
   * List cards
   */
  private async listCards(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const boardId = this.extractBoardId(command, context);
      const listId = this.extractListId(command, context);
      const filters = this.extractCardFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          board_id: boardId,
          list_id: listId,
          include_archived: filters.includeArchived,
          filters,
          limit: this.extractLimit(command) || 200
        })
      });

      const data = await response.json();

      if (data.ok) {
        const cards = data.cards;
        const summary = this.generateCardsSummary(cards);
        
        return {
          success: true,
          data: {
            cards,
            summary,
            total: data.total_count
          },
          action: 'list_cards',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list cards',
        action: 'list_cards',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_cards',
        platform: 'trello'
      };
    }
  }

  /**
   * Create card
   */
  private async createCard(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const cardInfo = this.extractCardInfo(command, context);
      
      if (!cardInfo.name) {
        return {
          success: false,
          error: 'Card title is required. Example: "create card [title] with description [description]"',
          action: 'create_card',
          platform: 'trello'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/trello/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: cardInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            card: data.card,
            url: data.card.url,
            message: `Card "${cardInfo.name}" created successfully`
          },
          action: 'create_card',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create card',
        action: 'create_card',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_card',
        platform: 'trello'
      };
    }
  }

  /**
   * Search cards
   */
  private async searchCards(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search cards deadline"',
          action: 'search_cards',
          platform: 'trello'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/trello/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'cards',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            cards: data.cards,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_cards',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search cards',
        action: 'search_cards',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_cards',
        platform: 'trello'
      };
    }
  }

  /**
   * List members
   */
  private async listMembers(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const boardId = this.extractBoardId(command, context);
      const filters = this.extractMemberFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          board_id: boardId,
          include_guests: filters.includeGuests,
          limit: this.extractLimit(command) || 100
        })
      });

      const data = await response.json();

      if (data.ok) {
        const members = data.members;
        const summary = this.generateMembersSummary(members);
        
        return {
          success: true,
          data: {
            members,
            summary,
            total: data.total_count
          },
          action: 'list_members',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list members',
        action: 'list_members',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_members',
        platform: 'trello'
      };
    }
  }

  /**
   * Get user profile
   */
  private async getUserProfile(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/user/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            user: data.user,
            enterprise: data.enterprise
          },
          action: 'get_user_profile',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to get user profile',
        action: 'get_user_profile',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'get_user_profile',
        platform: 'trello'
      };
    }
  }

  /**
   * Create task (simplified card creation)
   */
  private async createTask(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const taskInfo = this.extractTaskInfo(command, context);
      
      if (!taskInfo.title && !taskInfo.name) {
        return {
          success: false,
          error: 'Task title is required. Example: "create task [title] with description [description]"',
          action: 'create_task',
          platform: 'trello'
        };
      }

      // Use card creation endpoint
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...taskInfo,
            list_id: taskInfo.listId || 'todo',
            board_id: taskInfo.boardId || 'main'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            card: data.card,
            url: data.card.url,
            message: `Task "${taskInfo.title || taskInfo.name}" created successfully`
          },
          action: 'create_task',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create task',
        action: 'create_task',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_task',
        platform: 'trello'
      };
    }
  }

  /**
   * Create story (feature card)
   */
  private async createStory(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const storyInfo = this.extractStoryInfo(command, context);
      
      if (!storyInfo.title && !storyInfo.name) {
        return {
          success: false,
          error: 'Story title is required. Example: "create story [title] with description [description]"',
          action: 'create_story',
          platform: 'trello'
        };
      }

      // Use card creation endpoint with story specific settings
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...storyInfo,
            labels: storyInfo.labels || ['feature', 'story'],
            list_id: storyInfo.listId || 'backlog',
            board_id: storyInfo.boardId || 'main'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            card: data.card,
            url: data.card.url,
            message: `Story "${storyInfo.title || storyInfo.name}" created successfully`
          },
          action: 'create_story',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create story',
        action: 'create_story',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_story',
        platform: 'trello'
      };
    }
  }

  /**
   * Create bug (bug report card)
   */
  private async createBug(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const bugInfo = this.extractBugInfo(command, context);
      
      if (!bugInfo.title && !bugInfo.name) {
        return {
          success: false,
          error: 'Bug title is required. Example: "create bug [title] with description [description]"',
          action: 'create_bug',
          platform: 'trello'
        };
      }

      // Use card creation endpoint with bug specific settings
      const response = await fetch(`${this.baseUrl}/api/integrations/trello/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: {
            ...bugInfo,
            labels: bugInfo.labels || ['bug', 'urgent'],
            list_id: bugInfo.listId || 'bugs',
            board_id: bugInfo.boardId || 'main'
          }
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            card: data.card,
            url: data.card.url,
            message: `Bug "${bugInfo.title || bugInfo.name}" created successfully`
          },
          action: 'create_bug',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create bug',
        action: 'create_bug',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_bug',
        platform: 'trello'
      };
    }
  }

  /**
   * Global search across Trello
   */
  private async globalSearch(command: string, context?: any): Promise<TrelloSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search project deadline"',
          action: 'global_search',
          platform: 'trello'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/trello/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'global',
          limit: this.extractLimit(command) || 50
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            results: data.results,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'global_search',
          platform: 'trello'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search Trello',
        action: 'global_search',
        platform: 'trello'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'global_search',
        platform: 'trello'
      };
    }
  }

  // Helper methods for extracting information from commands
  
  private extractLimit(command: string): number | null {
    const limitMatch = command.match(/limit\s+(\d+)/i);
    return limitMatch ? parseInt(limitMatch[1]) : null;
  }

  private extractSearchQuery(command: string): string {
    const patterns = [
      /search\s+for\s+["']([^"']+)["']/i,
      /search\s+["']([^"']+)["']/i,
      /find\s+["']([^"']+)["']/i,
      /search\s+(\w+)/i,
      /find\s+(\w+)/i
    ];

    for (const pattern of patterns) {
      const match = command.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }

    return '';
  }

  private extractBoardId(command: string, context?: any): string | null {
    // First check context for board reference
    if (context?.boardId) return context.boardId;
    if (context?.board?.id) return context.board.id;

    // Extract from command
    const boardMatch = command.match(/(?:board)\s+["']?([^"']+)["']?/i);
    if (boardMatch) {
      // In real implementation, this would resolve board name to ID
      return boardMatch[1];
    }

    return null;
  }

  private extractListId(command: string, context?: any): string | null {
    // First check context for list reference
    if (context?.listId) return context.listId;
    if (context?.list?.id) return context.list.id;

    // Extract from command
    const listMatch = command.match(/(?:list)\s+["']?([^"']+)["']?/i);
    if (listMatch) {
      // In real implementation, this would resolve list name to ID
      return listMatch[1];
    }

    return null;
  }

  private extractCardInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:card|task)\s+(?:with\s+(?:title|name)|titled?)\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.name = titleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.desc = descMatch[1];
    }

    // Extract due date
    const dueMatch = command.match(/(?:due|deadline)\s+(\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4})/i);
    if (dueMatch) {
      info.due = new Date(dueMatch[1]).toISOString();
    }

    // Extract labels
    const labelsMatch = command.match(/(?:labels?|tags?)\s+["']([^"']+)["']/i);
    if (labelsMatch) {
      info.labels = labelsMatch[1].split(',').map((label: string) => label.trim());
    }

    // Extract assignees
    const assigneeMatch = command.match(/(?:assign|assigned?\s+to)\s+["']?([^"'\s]+)["']?/i);
    if (assigneeMatch) {
      info.idMembers = [assigneeMatch[1]];
    }

    // Extract board/list
    const boardMatch = command.match(/(?:in|within)\s+board\s+["']?([^"']+)["']?/i);
    if (boardMatch) {
      info.boardName = boardMatch[1];
    }

    const listMatch = command.match(/(?:in|within)\s+list\s+["']?([^"']+)["']?/i);
    if (listMatch) {
      info.listName = listMatch[1];
    }

    // Extract from context
    if (context?.boardId) info.idBoard = context.boardId;
    if (context?.listId) info.idList = context.listId;

    return info;
  }

  private extractTaskInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:task|todo)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    // Extract due date
    const dueMatch = command.match(/(?:due|deadline)\s+(\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4})/i);
    if (dueMatch) {
      info.due = new Date(dueMatch[1]).toISOString();
    }

    // Extract priority (labels)
    const priorityMatch = command.match(/(?:priority)\s+(high|medium|low)/i);
    if (priorityMatch) {
      info.labels = [priorityMatch[1]];
    }

    // Extract board/list
    const boardMatch = command.match(/(?:in|within)\s+board\s+["']?([^"']+)["']?/i);
    if (boardMatch) {
      info.boardId = boardMatch[1];
    }

    const listMatch = command.match(/(?:in|within)\s+list\s+["']?([^"']+)["']?/i);
    if (listMatch) {
      info.listId = listMatch[1];
    }

    return info;
  }

  private extractStoryInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:story|feature)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    // Extract points
    const pointsMatch = command.match(/(?:points|effort)\s+(\d+)/i);
    if (pointsMatch) {
      info.points = parseInt(pointsMatch[1]);
    }

    // Extract board/list
    const boardMatch = command.match(/(?:in|within)\s+board\s+["']?([^"']+)["']?/i);
    if (boardMatch) {
      info.boardId = boardMatch[1];
    }

    const listMatch = command.match(/(?:in|within)\s+list\s+["']?([^"']+)["']?/i);
    if (listMatch) {
      info.listId = listMatch[1];
    }

    return info;
  }

  private extractBugInfo(command: string, context?: any): any {
    const info: any = {};

    // Extract title/name
    const titleMatch = command.match(/(?:bug|issue)\s+(?:titled?)?\s+["']?([^"'\s]+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:with\s+(?:description|desc)|containing?)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    // Extract severity
    const severityMatch = command.match(/(?:severity|level)\s+(critical|high|medium|low)/i);
    if (severityMatch) {
      info.labels = [severityMatch[1]];
    }

    // Extract browser/environment
    const envMatch = command.match(/(?:in|on)\s+(["']?[^"'\s]+["']?)/i);
    if (envMatch) {
      info.environment = envMatch[1];
    }

    // Extract board/list
    const boardMatch = command.match(/(?:in|within)\s+board\s+["']?([^"']+)["']?/i);
    if (boardMatch) {
      info.boardId = boardMatch[1];
    }

    const listMatch = command.match(/(?:in|within)\s+list\s+["']?([^"']+)["']?/i);
    if (listMatch) {
      info.listId = listMatch[1];
    }

    return info;
  }

  private extractIncludeClosed(command: string): boolean {
    return command.includes('closed') || command.includes('archived');
  }

  private extractIncludeArchived(command: string): boolean {
    return command.includes('archived');
  }

  private extractListFilters(command: string): any {
    const filters: any = {};

    if (command.includes('archived')) {
      filters.includeClosed = true;
    }

    if (command.includes('subscribed')) {
      filters.subscribed = true;
    }

    return filters;
  }

  private extractCardFilters(command: string): any {
    const filters: any = {};

    if (command.includes('archived')) {
      filters.includeArchived = true;
    }

    if (command.includes('overdue') || command.includes('late')) {
      filters.overdue = true;
    }

    if (command.includes('due') || command.includes('deadline')) {
      filters.hasDue = true;
    }

    return filters;
  }

  private extractMemberFilters(command: string): any {
    const filters: any = {};

    if (command.includes('guests')) {
      filters.includeGuests = true;
    }

    if (command.includes('inactive')) {
      filters.includeInactive = true;
    }

    if (command.includes('active')) {
      filters.includeActive = true;
    }

    return filters;
  }

  // Summary generators
  
  private generateBoardsSummary(boards: any[]): string {
    const total = boards.length;
    const closedCount = boards.filter(b => b.closed).length;
    const starredCount = boards.filter(b => b.starred).length;

    return `Found ${total} boards: ${closedCount} closed, ${starredCount} starred`;
  }

  private generateListsSummary(lists: any[]): string {
    const total = lists.length;
    const closedCount = lists.filter(l => l.closed).length;

    return `Found ${total} lists: ${closedCount} archived`;
  }

  private generateCardsSummary(cards: any[]): string {
    const total = cards.length;
    const archivedCount = cards.filter(c => c.closed).length;
    const dueCount = cards.filter(c => c.due).length;
    const completedCount = cards.filter(c => c.dueComplete).length;

    return `Found ${total} cards: ${archivedCount} archived, ${dueCount} with due dates, ${completedCount} completed`;
  }

  private generateMembersSummary(members: any[]): string {
    const total = members.length;
    const adminCount = members.filter(m => m.memberType === 'admin').length;
    const guestCount = members.filter(m => m.memberType === 'guest').length;

    return `Found ${total} members: ${adminCount} admins, ${guestCount} guests`;
  }
}

// Export singleton instance
export const enhancedTrelloSkills = new EnhancedTrelloSkills();

// Export types
export type { TrelloSkillResult };