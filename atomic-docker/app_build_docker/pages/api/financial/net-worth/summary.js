"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const auth_helpers_nextjs_1 = require("@supabase/auth-helpers-nextjs");
async function handler(req, res) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }
    try {
        const supabase = (0, auth_helpers_nextjs_1.createServerSupabaseClient)({ req, res });
        const { data: { session }, } = await supabase.auth.getSession();
        if (!session) {
            return res.status(401).json({ error: 'Unauthorized' });
        }
        const userId = session.user.id;
        const { includeHistory = false, dateRange } = req.query;
        // Fetch all accounts for the user
        const { data: plaidAccounts } = await supabase
            .from('accounts')
            .select('balance, account_type')
            .eq('user_id', userId);
        const { data: manualAccounts } = await supabase
            .from('manual_accounts')
            .select('balance, account_type')
            .eq('user_id', userId);
        // Calculate net worth
        let totalAssets = 0;
        let totalLiabilities = 0;
        const allAccounts = [...(plaidAccounts || []), ...(manualAccounts || [])];
        allAccounts.forEach((account) => {
            const accountType = String(account.account_type).toLowerCase();
            // Define asset types
            const assetTypes = [
                'savings',
                'checking',
                'current',
                'investment',
                'brokerage',
                'retirement',
                'IRA',
                '401k',
                'money_market',
                'bond',
                'stock',
            ];
            const liabilityTypes = [
                'credit',
                'loan',
                'mortgage',
                'liability',
                'debt',
                'line_of_credit',
            ];
            let isAsset = false;
            let isLiability = false;
            // Check if it's an asset
            for (const type of assetTypes) {
                if (accountType.includes(type) ||
                    String(account.account_type || '')
                        .toLowerCase()
                        .includes(type)) {
                    isAsset = true;
                    break;
                }
            }
            // Check if it's a liability
            for (const type of liabilityTypes) {
                if (accountType.includes(type) ||
                    String(account.account_type || '')
                        .toLowerCase()
                        .includes(type)) {
                    isLiability = true;
                    break;
                }
            }
            // Handle balance sign
            const balance = Number(account.balance || 0);
            if (isAsset) {
                totalAssets += Math.abs(balance);
            }
            else if (isLiability) {
                totalLiabilities += Math.abs(balance);
            }
            else {
                // Default to asset for positive balances, liability for negative
                totalAssets += Math.max(0, balance);
                totalLiabilities += Math.max(0, -balance);
            }
        });
        const netWorth = totalAssets - totalLiabilities;
        // Fetch historical snapshots if requested
        let history = [];
        if (includeHistory === 'true' || includeHistory === true) {
            const { data: snapshots } = await supabase
                .from('net_worth_snapshots')
                .select('snapshot_date, net_worth')
                .eq('user_id', userId)
                .order('snapshot_date', { ascending: true });
            history =
                snapshots?.map((snap) => ({
                    date: snap.snapshot_date,
                    netWorth: Number(snap.net_worth),
                })) || [];
        }
        // Only include last 12 months for history
        if (history.length > 0) {
            const cutoffDate = new Date();
            cutoffDate.setMonth(cutoffDate.getMonth() - 12);
            history = history.filter((h) => new Date(h.date) >= cutoffDate);
        }
        // Calculate change (mock data if no history)
        let change = 0;
        let changePercent = 0;
        if (history.length > 1) {
            const firstValue = history[0]?.netWorth || 0;
            const lastValue = history[history.length - 1]?.netWorth || 0;
            change = lastValue - firstValue;
            changePercent = firstValue > 0 ? (change / firstValue) * 100 : 0;
        }
        else {
            // Mock change for demo purposes
            change = Math.random() * 1000 - 500;
            changePercent = (change / Math.abs(netWorth || 1)) * 100;
        }
        const result = {
            current: netWorth,
            change,
            changePercent,
            assets: totalAssets,
            liabilities: totalLiabilities,
            history,
        };
        res.status(200).json({ data: result });
    }
    catch (error) {
        console.error('Net worth summary error:', error);
        res.status(500).json({ error: 'Failed to calculate net worth' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3VtbWFyeS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInN1bW1hcnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFHQSwwQkErSkM7QUFqS0QsdUVBQTJFO0FBRTVELEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksR0FBRyxDQUFDLE1BQU0sS0FBSyxLQUFLLEVBQUUsQ0FBQztRQUN6QixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsS0FBSyxFQUFFLG9CQUFvQixFQUFFLENBQUMsQ0FBQztJQUMvRCxDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxRQUFRLEdBQUcsSUFBQSxnREFBMEIsRUFBQyxFQUFFLEdBQUcsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO1FBQzFELE1BQU0sRUFDSixJQUFJLEVBQUUsRUFBRSxPQUFPLEVBQUUsR0FDbEIsR0FBRyxNQUFNLFFBQVEsQ0FBQyxJQUFJLENBQUMsVUFBVSxFQUFFLENBQUM7UUFFckMsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ2IsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxjQUFjLEVBQUUsQ0FBQyxDQUFDO1FBQ3pELENBQUM7UUFFRCxNQUFNLE1BQU0sR0FBRyxPQUFPLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FBQztRQUMvQixNQUFNLEVBQUUsY0FBYyxHQUFHLEtBQUssRUFBRSxTQUFTLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO1FBRXhELGtDQUFrQztRQUNsQyxNQUFNLEVBQUUsSUFBSSxFQUFFLGFBQWEsRUFBRSxHQUFHLE1BQU0sUUFBUTthQUMzQyxJQUFJLENBQUMsVUFBVSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyx1QkFBdUIsQ0FBQzthQUMvQixFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0s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bXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgeyBjcmVhdGVTZXJ2ZXJTdXBhYmFzZUNsaWVudCB9IGZyb20gJ0BzdXBhYmFzZS9hdXRoLWhlbHBlcnMtbmV4dGpzJztcblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBpZiAocmVxLm1ldGhvZCAhPT0gJ0dFVCcpIHtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDUpLmpzb24oeyBlcnJvcjogJ01ldGhvZCBub3QgYWxsb3dlZCcgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHN1cGFiYXNlID0gY3JlYXRlU2VydmVyU3VwYWJhc2VDbGllbnQoeyByZXEsIHJlcyB9KTtcbiAgICBjb25zdCB7XG4gICAgICBkYXRhOiB7IHNlc3Npb24gfSxcbiAgICB9ID0gYXdhaXQgc3VwYWJhc2UuYXV0aC5nZXRTZXNzaW9uKCk7XG5cbiAgICBpZiAoIXNlc3Npb24pIHtcbiAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuanNvbih7IGVycm9yOiAnVW5hdXRob3JpemVkJyB9KTtcbiAgICB9XG5cbiAgICBjb25zdCB1c2VySWQgPSBzZXNzaW9uLnVzZXIuaWQ7XG4gICAgY29uc3QgeyBpbmNsdWRlSGlzdG9yeSA9IGZhbHNlLCBkYXRlUmFuZ2UgfSA9IHJlcS5xdWVyeTtcblxuICAgIC8vIEZldGNoIGFsbCBhY2NvdW50cyBmb3IgdGhlIHVzZXJcbiAgICBjb25zdCB7IGRhdGE6IHBsYWlkQWNjb3VudHMgfSA9IGF3YWl0IHN1cGFiYXNlXG4gICAgICAuZnJvbSgnYWNjb3VudHMnKVxuICAgICAgLnNlbGVjdCgnYmFsYW5jZSwgYWNjb3VudF90eXBlJylcbiAgICAgIC5lcSgndXNlcl9pZCcsIHVzZXJJZCk7XG5cbiAgICBjb25zdCB7IGRhdGE6IG1hbnVhbEFjY291bnRzIH0gPSBhd2FpdCBzdXBhYmFzZVxuICAgICAgLmZyb20oJ21hbnVhbF9hY2NvdW50cycpXG4gICAgICAuc2VsZWN0KCdiYWxhbmNlLCBhY2NvdW50X3R5cGUnKVxuICAgICAgLmVxKCd1c2VyX2lkJywgdXNlcklkKTtcblxuICAgIC8vIENhbGN1bGF0ZSBuZXQgd29ydGhcbiAgICBsZXQgdG90YWxBc3NldHMgPSAwO1xuICAgIGxldCB0b3RhbExpYWJpbGl0aWVzID0gMDtcbiAgICBjb25zdCBhbGxBY2NvdW50cyA9IFsuLi4ocGxhaWRBY2NvdW50cyB8fCBbXSksIC4uLihtYW51YWxBY2NvdW50cyB8fCBbXSldO1xuXG4gICAgYWxsQWNjb3VudHMuZm9yRWFjaCgoYWNjb3VudCkgPT4ge1xuICAgICAgY29uc3QgYWNjb3VudFR5cGUgPSBTdHJpbmcoYWNjb3VudC5hY2NvdW50X3R5cGUpLnRvTG93ZXJDYXNlKCk7XG5cbiAgICAgIC8vIERlZmluZSBhc3NldCB0eXBlc1xuICAgICAgY29uc3QgYXNzZXRUeXBlcyA9IFtcbiAgICAgICAgJ3NhdmluZ3MnLFxuICAgICAgICAnY2hlY2tpbmcnLFxuICAgICAgICAnY3VycmVudCcsXG4gICAgICAgICdpbnZlc3RtZW50JyxcbiAgICAgICAgJ2Jyb2tlcmFnZScsXG4gICAgICAgICdyZXRpcmVtZW50JyxcbiAgICAgICAgJ0lSQScsXG4gICAgICAgICc0MDFrJyxcbiAgICAgICAgJ21vbmV5X21hcmtldCcsXG4gICAgICAgICdib25kJyxcbiAgICAgICAgJ3N0b2NrJyxcbiAgICAgIF07XG4gICAgICBjb25zdCBsaWFiaWxpdHlUeXBlcyA9IFtcbiAgICAgICAgJ2NyZWRpdCcsXG4gICAgICAgICdsb2FuJyxcbiAgICAgICAgJ21vcnRnYWdlJyxcbiAgICAgICAgJ2xpYWJpbGl0eScsXG4gICAgICAgICdkZWJ0JyxcbiAgICAgICAgJ2xpbmVfb2ZfY3JlZGl0JyxcbiAgICAgIF07XG5cbiAgICAgIGxldCBpc0Fzc2V0ID0gZmFsc2U7XG4gICAgICBsZXQgaXNMaWFiaWxpdHkgPSBmYWxzZTtcblxuICAgICAgLy8gQ2hlY2sgaWYgaXQncyBhbiBhc3NldFxuICAgICAgZm9yIChjb25zdCB0eXBlIG9mIGFzc2V0VHlwZXMpIHtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGFjY291bnRUeXBlLmluY2x1ZGVzKHR5cGUpIHx8XG4gICAgICAgICAgU3RyaW5nKGFjY291bnQuYWNjb3VudF90eXBlIHx8ICcnKVxuICAgICAgICAgICAgLnRvTG93ZXJDYXNlKClcbiAgICAgICAgICAgIC5pbmNsdWRlcyh0eXBlKVxuICAgICAgICApIHtcbiAgICAgICAgICBpc0Fzc2V0ID0gdHJ1ZTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICAvLyBDaGVjayBpZiBpdCdzIGEgbGlhYmlsaXR5XG4gICAgICBmb3IgKGNvbnN0IHR5cGUgb2YgbGlhYmlsaXR5VHlwZXMpIHtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGFjY291bnRUeXBlLmluY2x1ZGVzKHR5cGUpIHx8XG4gICAgICAgICAgU3RyaW5nKGFjY291bnQuYWNjb3VudF90eXBlIHx8ICcnKVxuICAgICAgICAgICAgLnRvTG93ZXJDYXNlKClcbiAgICAgICAgICAgIC5pbmNsdWRlcyh0eXBlKVxuICAgICAgICApIHtcbiAgICAgICAgICBpc0xpYWJpbGl0eSA9IHRydWU7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgLy8gSGFuZGxlIGJhbGFuY2Ugc2lnblxuICAgICAgY29uc3QgYmFsYW5jZSA9IE51bWJlcihhY2NvdW50LmJhbGFuY2UgfHwgMCk7XG5cbiAgICAgIGlmIChpc0Fzc2V0KSB7XG4gICAgICAgIHRvdGFsQXNzZXRzICs9IE1hdGguYWJzKGJhbGFuY2UpO1xuICAgICAgfSBlbHNlIGlmIChpc0xpYWJpbGl0eSkge1xuICAgICAgICB0b3RhbExpYWJpbGl0aWVzICs9IE1hdGguYWJzKGJhbGFuY2UpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgLy8gRGVmYXVsdCB0byBhc3NldCBmb3IgcG9zaXRpdmUgYmFsYW5jZXMsIGxpYWJpbGl0eSBmb3IgbmVnYXRpdmVcbiAgICAgICAgdG90YWxBc3NldHMgKz0gTWF0aC5tYXgoMCwgYmFsYW5jZSk7XG4gICAgICAgIHRvdGFsTGlhYmlsaXRpZXMgKz0gTWF0aC5tYXgoMCwgLWJhbGFuY2UpO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgY29uc3QgbmV0V29ydGggPSB0b3RhbEFzc2V0cyAtIHRvdGFsTGlhYmlsaXRpZXM7XG5cbiAgICAvLyBGZXRjaCBoaXN0b3JpY2FsIHNuYXBzaG90cyBpZiByZXF1ZXN0ZWRcbiAgICBsZXQgaGlzdG9yeSA9IFtdO1xuICAgIGlmIChpbmNsdWRlSGlzdG9yeSA9PT0gJ3RydWUnIHx8IGluY2x1ZGVIaXN0b3J5ID09PSB0cnVlKSB7XG4gICAgICBjb25zdCB7IGRhdGE6IHNuYXBzaG90cyB9ID0gYXdhaXQgc3VwYWJhc2VcbiAgICAgICAgLmZyb20oJ25ldF93b3J0aF9zbmFwc2hvdHMnKVxuICAgICAgICAuc2VsZWN0KCdzbmFwc2hvdF9kYXRlLCBuZXRfd29ydGgnKVxuICAgICAgICAuZXEoJ3VzZXJfaWQnLCB1c2VySWQpXG4gICAgICAgIC5vcmRlcignc25hcHNob3RfZGF0ZScsIHsgYXNjZW5kaW5nOiB0cnVlIH0pO1xuXG4gICAgICBoaXN0b3J5ID1cbiAgICAgICAgc25hcHNob3RzPy5tYXAoKHNuYXApID0+ICh7XG4gICAgICAgICAgZGF0ZTogc25hcC5zbmFwc2hvdF9kYXRlLFxuICAgICAgICAgIG5ldFdvcnRoOiBOdW1iZXIoc25hcC5uZXRfd29ydGgpLFxuICAgICAgICB9KSkgfHwgW107XG4gICAgfVxuXG4gICAgLy8gT25seSBpbmNsdWRlIGxhc3QgMTIgbW9udGhzIGZvciBoaXN0b3J5XG4gICAgaWYgKGhpc3RvcnkubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgY3V0b2ZmRGF0ZSA9IG5ldyBEYXRlKCk7XG4gICAgICBjdXRvZmZEYXRlLnNldE1vbnRoKGN1dG9mZkRhdGUuZ2V0TW9udGgoKSAtIDEyKTtcbiAgICAgIGhpc3RvcnkgPSBoaXN0b3J5LmZpbHRlcigoaCkgPT4gbmV3IERhdGUoaC5kYXRlKSA+PSBjdXRvZmZEYXRlKTtcbiAgICB9XG5cbiAgICAvLyBDYWxjdWxhdGUgY2hhbmdlIChtb2NrIGRhdGEgaWYgbm8gaGlzdG9yeSlcbiAgICBsZXQgY2hhbmdlID0gMDtcbiAgICBsZXQgY2hhbmdlUGVyY2VudCA9IDA7XG4gICAgaWYgKGhpc3RvcnkubGVuZ3RoID4gMSkge1xuICAgICAgY29uc3QgZmlyc3RWYWx1ZSA9IGhpc3RvcnlbMF0/Lm5ldFdvcnRoIHx8IDA7XG4gICAgICBjb25zdCBsYXN0VmFsdWUgPSBoaXN0b3J5W2hpc3RvcnkubGVuZ3RoIC0gMV0/Lm5ldFdvcnRoIHx8IDA7XG4gICAgICBjaGFuZ2UgPSBsYXN0VmFsdWUgLSBmaXJzdFZhbHVlO1xuICAgICAgY2hhbmdlUGVyY2VudCA9IGZpcnN0VmFsdWUgPiAwID8gKGNoYW5nZSAvIGZpcnN0VmFsdWUpICogMTAwIDogMDtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gTW9jayBjaGFuZ2UgZm9yIGRlbW8gcHVycG9zZXNcbiAgICAgIGNoYW5nZSA9IE1hdGgucmFuZG9tKCkgKiAxMDAwIC0gNTAwO1xuICAgICAgY2hhbmdlUGVyY2VudCA9IChjaGFuZ2UgLyBNYXRoLmFicyhuZXRXb3J0aCB8fCAxKSkgKiAxMDA7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzdWx0ID0ge1xuICAgICAgY3VycmVudDogbmV0V29ydGgsXG4gICAgICBjaGFuZ2UsXG4gICAgICBjaGFuZ2VQZXJjZW50LFxuICAgICAgYXNzZXRzOiB0b3RhbEFzc2V0cyxcbiAgICAgIGxpYWJpbGl0aWVzOiB0b3RhbExpYWJpbGl0aWVzLFxuICAgICAgaGlzdG9yeSxcbiAgICB9O1xuXG4gICAgcmVzLnN0YXR1cygyMDApLmpzb24oeyBkYXRhOiByZXN1bHQgfSk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignTmV0IHdvcnRoIHN1bW1hcnkgZXJyb3I6JywgZXJyb3IpO1xuICAgIHJlcy5zdGF0dXMoNTAwKS5qc29uKHsgZXJyb3I6ICdGYWlsZWQgdG8gY2FsY3VsYXRlIG5ldCB3b3J0aCcgfSk7XG4gIH1cbn1cbiJdfQ==