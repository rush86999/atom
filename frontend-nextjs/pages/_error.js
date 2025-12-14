/**
 * Custom error page for better user experience
 */

function Error({ statusCode, err }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      fontFamily: 'Arial, sans-serif',
      textAlign: 'center',
      padding: '20px'
    }}>
      <h1 style={{ color: '#e53e3e', fontSize: '2rem' }}>
        {statusCode ? `Error ${statusCode}` : 'An error occurred'}
      </h1>

      <p style={{ fontSize: '1.2rem', margin: '20px 0', color: '#4a5568' }}>
        {statusCode === 404 && 'The page you are looking for does not exist.'}
        {statusCode === 500 && 'Internal server error. Please try again later.'}
        {statusCode && ![404, 500].includes(statusCode) && 'Something went wrong. Please try again.'}
        {!statusCode && 'An unexpected error occurred. Please refresh the page.'}
      </p>

      <div style={{ marginTop: '30px' }}>
        <button
          onClick={() => window.location.href = '/'}
          style={{
            backgroundColor: '#3182ce',
            color: 'white',
            padding: '12px 24px',
            border: 'none',
            borderRadius: '6px',
            fontSize: '1rem',
            cursor: 'pointer',
            marginRight: '10px'
          }}
        >
          Go Home
        </button>

        <button
          onClick={() => window.location.reload()}
          style={{
            backgroundColor: '#48bb78',
            color: 'white',
            padding: '12px 24px',
            border: 'none',
            borderRadius: '6px',
            fontSize: '1rem',
            cursor: 'pointer'
          }}
        >
          Refresh Page
        </button>
      </div>

      {process.env.NODE_ENV === 'development' && err && (
        <details style={{ marginTop: '30px', textAlign: 'left', maxWidth: '600px' }}>
          <summary style={{ cursor: 'pointer', color: '#e53e3e' }}>
            Error Details (Development Only)
          </summary>
          <pre style={{
            backgroundColor: '#f7fafc',
            padding: '15px',
            borderRadius: '4px',
            overflow: 'auto',
            fontSize: '0.9rem'
          }}>
            {err.stack}
          </pre>
        </details>
      )}
    </div>
  );
}

Error.getInitialProps = ({ res, err }) => {
  const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
  return { statusCode, err };
};

export default Error;