import express from 'express';
import { Request, Response } from 'express';
import paypal from 'paypal-rest-sdk';
import { getPaypalAccessToken } from '@lib/api-helper';

const router = express.Router();

// Middleware to get the user's access token and configure the PayPal SDK
const paypalMiddleware = async (req: Request, res: Response, next: Function) => {
    const userId = (req as any).user.sub;
    if (!userId) {
        return res.status(401).send('Unauthorized: User ID not found.');
    }

    try {
        const accessToken = await getPaypalAccessToken(userId);
        if (!accessToken) {
            return res.status(403).send('Forbidden: PayPal access token not found.');
        }

        paypal.configure({
            'mode': 'sandbox', //sandbox or live
            'client_id': process.env.PAYPAL_CLIENT_ID,
            'client_secret': process.env.PAYPAL_CLIENT_SECRET,
            'headers' : {
                'custom': 'header'
            }
        });

        (req as any).paypal = paypal;
        next();
    } catch (error) {
        console.error('Error configuring PayPal SDK:', error);
        res.status(500).send('Internal Server Error');
    }
};

router.use(paypalMiddleware);

// Route to get the user's PayPal balance
router.get('/balance', async (req, res) => {
    try {
        // This is a placeholder. The PayPal REST API does not have a direct endpoint for getting the account balance.
        // You would need to use the Transaction Search API to calculate the balance.
        res.json({ balance: 'not implemented' });
    } catch (error) {
        console.error('Error getting balance:', error);
        res.status(500).send('Internal Server Error');
    }
});

// Route to get the user's recent transactions
router.get('/transactions', async (req, res) => {
    try {
        const paypalClient = (req as any).paypal;
        paypalClient.payment.list({ count: 10 }, (error, payments) => {
            if (error) {
                throw error;
            } else {
                res.json(payments);
            }
        });
    } catch (error) {
        console.error('Error getting transactions:', error);
        res.status(500).send('Internal Server Error');
    }
});

export default router;
