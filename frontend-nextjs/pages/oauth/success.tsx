import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

export default function OAuthSuccess() {
    const router = useRouter();
    const { provider } = router.query;
    const [countdown, setCountdown] = useState(3);

    useEffect(() => {
        const timer = setInterval(() => {
            setCountdown((prev) => {
                if (prev <= 1) {
                    router.push('/');
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(timer);
    }, [router]);

    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            fontFamily: 'Arial, sans-serif'
        }}>
            <div style={{ textAlign: 'center', maxWidth: '500px', padding: '40px' }}>
                <div style={{ fontSize: '64px', marginBottom: '20px' }}>✅</div>
                <h1 style={{ color: '#22c55e', marginBottom: '10px' }}>Authentication Successful!</h1>
                <p style={{ color: '#6b7280', marginBottom: '30px' }}>
                    You have successfully connected {provider || 'your account'} to ATOM.
                </p>
                <p style={{ color: '#9ca3af', fontSize: '14px' }}>
                    Redirecting to home in {countdown} seconds...
                </p>
            </div>
        </div>
    );
}
