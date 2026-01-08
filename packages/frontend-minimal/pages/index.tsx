import type { NextPage } from 'next'
import Head from 'next/head'

const Home: NextPage = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>ATOM Agentic OS - Minimal Frontend</title>
        <meta name="description" content="Minimal frontend for ATOM Agentic OS e2e testing" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className="container mx-auto px-4 py-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            ATOM Agentic OS
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Minimal Frontend for E2E Testing
          </p>

          <div className="bg-white rounded-lg shadow-md p-6 max-w-2xl mx-auto">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              System Status
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 className="font-medium text-green-800">Frontend</h3>
                <p className="text-green-600">Operational</p>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="font-medium text-blue-800">Backend API</h3>
                <p className="text-blue-600">Connected</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-700">Version</span>
                <span className="font-medium">1.0.0</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-700">Environment</span>
                <span className="font-medium">Development</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-gray-700">Last Updated</span>
                <span className="font-medium">
                  {new Date().toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-8">
            <button
              onClick={() => window.location.reload()}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
            >
              Refresh Status
            </button>
          </div>
        </div>
      </main>

      <footer className="mt-12 border-t border-gray-200 py-6">
        <div className="container mx-auto px-4 text-center text-gray-500">
          <p>ATOM Agentic OS &copy; {new Date().getFullYear()}</p>
        </div>
      </footer>
    </div>
  )
}

export default Home
