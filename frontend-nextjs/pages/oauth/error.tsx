import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

export default function OAuthError() {
    const router = useRouter();
    const { error } = router.query;
    const [countdown, setCountdown] = useState(5);

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
                <div style={{ fontSize: '64px', marginBottom: '20px' }}>❌</div>
                <h1 style={{ color: '#ef4444', marginBottom: '10px' }}>Authentication Failed</h1>
                <p style={{ color: '#6b7280', marginBottom: '20px' }}>
                    There was a problem connecting your account.
                </p>
                {error && (
                    <div style={{
                        backgroundColor: '#fee2e2',
                        color: '#991b1b',
                        padding: '12px',
                        borderRadius: '8px',
                        marginBottom: '30px',
                        fontSize: '14px'
                    }}>
                        Error: {error}
                    </div>
                )}
                <p style={{ color: '#9ca3af', fontSize: '14px' }}>
                    Redirecting to home in {countdown} seconds...
                </p>
            </div>
        </div>
    );
}
