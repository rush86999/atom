import React, { useState, useEffect } from 'react';
import { getBudgetAlertSettings, updateBudgetAlertSettings } from '../../lib/api-backend-helper';
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

const BudgetAlerts = ({ sub: userId }) => {
  const [settings, setSettings] = useState({ is_enabled: true, threshold: 90 });

  useEffect(() => {
    if (userId) {
      fetchSettings();
    }
  }, [userId]);

  const fetchSettings = async () => {
    const response = await getBudgetAlertSettings(userId);
    if (response && response.data) {
      setSettings(response.data);
    }
  };

  const handleUpdateSettings = async () => {
    await updateBudgetAlertSettings(userId, settings);
    fetchSettings();
  };

  return (
    <div>
      <h1>Budget Alert Settings</h1>

      <div>
        <label>
          <input
            type="checkbox"
            checked={settings.is_enabled}
            onChange={(e) => setSettings({ ...settings, is_enabled: e.target.checked })}
          />
          Enable Budget Alerts
        </label>
      </div>

      <div>
        <label>
          Alert Threshold (% of budget)
          <input
            type="number"
            value={settings.threshold}
            onChange={(e) => setSettings({ ...settings, threshold: parseInt(e.target.value) })}
          />
        </label>
      </div>

      <button onClick={handleUpdateSettings}>Save Settings</button>
    </div>
  );
};

export default BudgetAlerts;
