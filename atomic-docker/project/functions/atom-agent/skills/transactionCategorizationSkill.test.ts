import {
  createTransactionRule,
  listTransactionRules,
  updateTransactionRule,
  deleteTransactionRule,
} from './transactionCategorizationSkill';
import { callHasura } from '../_utils/hasura';

jest.mock('../_utils/hasura');

const mockCallHasura = callHasura as jest.Mock;

describe('transactionCategorizationSkill', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createTransactionRule', () => {
    it('should create a new transaction rule', async () => {
      const userId = 'test-user';
      const rule = { pattern: 'Starbucks', target_value: 'Coffee' };
      const expectedResponse = { success: true, message: 'Transaction rule created successfully.', data: { id: 1 } };
      mockCallHasura.mockResolvedValue({ data: { insert_transaction_rules_one: { id: 1 } } });

      const response = await createTransactionRule(userId, rule);

      expect(response).toEqual(expectedResponse);
      expect(mockCallHasura).toHaveBeenCalledWith(expect.objectContaining({
        variables: {
          rule: expect.objectContaining({
            user_id: userId,
            pattern: rule.pattern,
            target_value: rule.target_value,
          }),
        },
      }));
    });
  });

  describe('listTransactionRules', () => {
    it('should list all transaction rules for a user', async () => {
      const userId = 'test-user';
      const rules = [{ id: 1, rule_name: 'Rule 1', pattern: 'Starbucks', target_value: 'Coffee' }];
      const expectedResponse = { success: true, message: 'Transaction rules listed successfully.', data: rules };
      mockCallHasura.mockResolvedValue({ data: { transaction_rules: rules } });

      const response = await listTransactionRules(userId);

      expect(response).toEqual(expectedResponse);
      expect(mockCallHasura).toHaveBeenCalledWith(expect.objectContaining({
        variables: { userId },
      }));
    });
  });

  describe('updateTransactionRule', () => {
    it('should update an existing transaction rule', async () => {
      const userId = 'test-user';
      const ruleId = 1;
      const updates = { pattern: 'Shell' };
      const expectedResponse = { success: true, message: 'Transaction rule updated successfully.', data: { id: 1 } };
      mockCallHasura.mockResolvedValueOnce({ data: { transaction_rules: [{ id: 1 }] } }); // For the check
      mockCallHasura.mockResolvedValueOnce({ data: { update_transaction_rules_by_pk: { id: 1 } } });


      const response = await updateTransactionRule(userId, ruleId, updates);

      expect(response).toEqual(expectedResponse);
      expect(mockCallHasura).toHaveBeenCalledWith(expect.objectContaining({
        variables: { ruleId, updates },
      }));
    });
  });

  describe('deleteTransactionRule', () => {
    it('should delete a transaction rule', async () => {
      const userId = 'test-user';
      const ruleId = 1;
      const expectedResponse = { success: true, message: 'Transaction rule deleted successfully.' };
      mockCallHasura.mockResolvedValueOnce({ data: { transaction_rules: [{ id: 1 }] } }); // For the check
      mockCallHasura.mockResolvedValueOnce({ data: { delete_transaction_rules_by_pk: { id: 1 } } });

      const response = await deleteTransactionRule(userId, ruleId);

      expect(response).toEqual(expectedResponse);
      expect(mockCallHasura).toHaveBeenCalledWith(expect.objectContaining({
        variables: { ruleId },
      }));
    });
  });
});
