import React, { useState, useEffect } from 'react';
import { listTransactionRules, createTransactionRule, deleteTransactionRule } from '../../lib/api-backend-helper';
import { NextApiRequest, NextApiResponse } from 'next';
import supertokensNode from 'supertokens-node'
import { backendConfig } from '@config/backendConfig'
import Session from 'supertokens-node/recipe/session'

export async function getServerSideProps({ req, res }: { req: NextApiRequest, res: NextApiResponse }) {
    supertokensNode.init(backendConfig())
    let session
    try {
        session = await Session.getSession(req, res, {
            overrideGlobalClaimValidators: async function () {
                return []
            },
        })
    } catch (err: any) {
        if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
            return { props: { fromSupertokens: 'needs-refresh' } }
        } else if (err.type === Session.Error.UNAUTHORISED) {
            return { props: { fromSupertokens: 'needs-refresh' } }
        }
        throw err
    }

    if (!session?.getUserId()) {
        return {
            redirect: {
                destination: '/User/Login/UserLogin',
                permanent: false,
            },
        }
    }

    return {
        props: {
        sub: session.getUserId(),
        }
    }
}

const TransactionRules = ({ sub: userId }) => {
  const [rules, setRules] = useState([]);
  const [newRule, setNewRule] = useState({ pattern: '', target_value: '' });

  useEffect(() => {
    if (userId) {
      fetchRules();
    }
  }, [userId]);

  const fetchRules = async () => {
    const response = await listTransactionRules(userId);
    if(response && response.data) {
      setRules(response.data);
    }
  };

  const handleCreateRule = async () => {
    await createTransactionRule(userId, newRule);
    fetchRules();
    setNewRule({ pattern: '', target_value: '' });
  };

  const handleDeleteRule = async (ruleId) => {
    await deleteTransactionRule(userId, ruleId);
    fetchRules();
  };

  return (
    <div>
      <h1>Transaction Categorization Rules</h1>

      <div>
        <h2>Create New Rule</h2>
        <input
          type="text"
          placeholder="Merchant Name (e.g., Starbucks)"
          value={newRule.pattern}
          onChange={(e) => setNewRule({ ...newRule, pattern: e.target.value })}
        />
        <input
          type="text"
          placeholder="Category (e.g., Coffee Shops)"
          value={newRule.target_value}
          onChange={(e) => setNewRule({ ...newRule, target_value: e.target.value })}
        />
        <button onClick={handleCreateRule}>Create Rule</button>
      </div>

      <div>
        <h2>Existing Rules</h2>
        <ul>
          {rules.map((rule : any) => (
            <li key={rule.id}>
              <span>{rule.rule_name}: {rule.pattern} -> {rule.target_value}</span>
              <button onClick={() => handleDeleteRule(rule.id)}>Delete</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default TransactionRules;
