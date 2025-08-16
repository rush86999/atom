import { SkillResponse } from '../types';
import { callHasura } from '../_utils/hasura';

interface TransactionRule {
  id: number;
  user_id: string;
  rule_name: string;
  pattern: string;
  pattern_type: 'regex' | 'contains' | 'exact';
  action: 'categorize';
  target_value: string;
  is_active: boolean;
  priority: number;
}

const CREATE_RULE_MUTATION = `
  mutation InsertTransactionRule($rule: transaction_rules_insert_input!) {
    insert_transaction_rules_one(object: $rule) {
      id
    }
  }
`;

const LIST_RULES_QUERY = `
  query GetTransactionRules($userId: String!) {
    transaction_rules(where: {user_id: {_eq: $userId}}) {
      id
      rule_name
      pattern
      pattern_type
      action
      target_value
      is_active
      priority
    }
  }
`;

const UPDATE_RULE_MUTATION = `
  mutation UpdateTransactionRule($ruleId: Int!, $updates: transaction_rules_set_input!) {
    update_transaction_rules_by_pk(pk_columns: {id: $ruleId}, _set: $updates) {
      id
    }
  }
`;

const DELETE_RULE_MUTATION = `
  mutation DeleteTransactionRule($ruleId: Int!) {
    delete_transaction_rules_by_pk(id: $ruleId) {
      id
    }
  }
`;


/**
 * Creates a new transaction categorization rule.
 * @param userId The ID of the user.
 * @param rule The rule to create.
 * @returns A promise that resolves with a skill response.
 */
export async function createTransactionRule(userId: string, rule: Partial<TransactionRule>): Promise<SkillResponse> {
  try {
    const ruleData = {
      user_id: userId,
      rule_name: rule.rule_name || `Rule for ${rule.pattern}`,
      pattern: rule.pattern,
      pattern_type: rule.pattern_type || 'contains',
      action: 'categorize',
      target_value: rule.target_value,
      is_active: rule.is_active !== undefined ? rule.is_active : true,
      priority: rule.priority || 0,
    };

    const response = await callHasura({
      query: CREATE_RULE_MUTATION,
      variables: { rule: ruleData },
    });

    if (response.errors) {
      throw new Error(response.errors[0].message);
    }

    return {
      success: true,
      message: 'Transaction rule created successfully.',
      data: response.data.insert_transaction_rules_one,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Error creating transaction rule: ${error.message}`,
    };
  }
}

/**
 * Lists all transaction categorization rules for a user.
 * @param userId The ID of the user.
 * @returns A promise that resolves with a skill response containing the list of rules.
 */
export async function listTransactionRules(userId: string): Promise<SkillResponse> {
  try {
    const response = await callHasura({
      query: LIST_RULES_QUERY,
      variables: { userId },
    });

    if (response.errors) {
      throw new Error(response.errors[0].message);
    }

    return {
      success: true,
      message: 'Transaction rules listed successfully.',
      data: response.data.transaction_rules,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Error listing transaction rules: ${error.message}`,
    };
  }
}

/**
 * Updates an existing transaction categorization rule.
 * @param userId The ID of the user.
 * @param ruleId The ID of the rule to update.
 * @param updates The updates to apply to the rule.
 * @returns A promise that resolves with a skill response.
 */
export async function updateTransactionRule(userId: string, ruleId: number, updates: Partial<TransactionRule>): Promise<SkillResponse> {
  try {
    // First, verify the rule belongs to the user.
    // This is important for security.
    // A more robust implementation would do this as part of the Hasura permissions.
    const listResponse = await listTransactionRules(userId);
    if (!listResponse.success) {
        throw new Error(listResponse.message);
    }
    const rules = listResponse.data as TransactionRule[];
    if (!rules.find(rule => rule.id === ruleId)) {
        return {
            success: false,
            message: 'Transaction rule not found or you do not have permission to update it.'
        }
    }

    const response = await callHasura({
      query: UPDATE_RULE_MUTATION,
      variables: { ruleId, updates },
    });

    if (response.errors) {
      throw new Error(response.errors[0].message);
    }

    return {
      success: true,
      message: 'Transaction rule updated successfully.',
      data: response.data.update_transaction_rules_by_pk,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Error updating transaction rule: ${error.message}`,
    };
  }
}

/**
 * Deletes a transaction categorization rule.
 * @param userId The ID of the user.
 * @param ruleId The ID of the rule to delete.
 * @returns A promise that resolves with a skill response.
 */
export async function deleteTransactionRule(userId: string, ruleId: number): Promise<SkillResponse> {
  try {
    // First, verify the rule belongs to the user.
    const listResponse = await listTransactionRules(userId);
    if (!listResponse.success) {
        throw new Error(listResponse.message);
    }
    const rules = listResponse.data as TransactionRule[];
    if (!rules.find(rule => rule.id === ruleId)) {
        return {
            success: false,
            message: 'Transaction rule not found or you do not have permission to delete it.'
        }
    }

    const response = await callHasura({
      query: DELETE_RULE_MUTATION,
      variables: { ruleId },
    });

    if (response.errors) {
      throw new Error(response.errors[0].message);
    }

    return {
      success: true,
      message: 'Transaction rule deleted successfully.',
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Error deleting transaction rule: ${error.message}`,
    };
  }
}
