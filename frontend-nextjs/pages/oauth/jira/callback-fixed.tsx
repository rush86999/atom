/**
 * ATOM Jira OAuth Callback Page
 * Handles OAuth flow completion for Jira integration
 */

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'

interface CallbackData {
  success?: boolean
  error?: string
  workspace?: string
}

const CallbackStatus: React.FC<{
  success: boolean
  workspace?: string
  onClose?: () => void
}> = ({ success, workspace, onClose }) => {
  const getStatusIcon = () => {
    return success ? '✅' : '❌'
  }

  const getStatusTitle = () => {
    return success ? 'Integration Successful!' : 'Integration Failed'
  }

  const getStatusMessage = () => {
    if (success) {
      return `Successfully connected to ${workspace || 'Jira'} workspace.`
    }
    return 'Failed to connect to Jira workspace. Please try again.'
  }

  return (
    <div className="text-center py-8">
      <div className="text-6xl mb-4">{getStatusIcon()}</div>
      <h2 className="text-2xl font-bold text-gray-800 mb-2">
        {getStatusTitle()}
      </h2>
      <p className="text-gray-600 mb-6">{getStatusMessage()}</p>

      <div className="space-x-4">
        {success ? (
          <button
            onClick={onClose}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
          >
            Continue to Dashboard
          </button>
        ) : (
          <button
            onClick={() => window.close()}
            className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
          >
            Close Window
          </button>
        )}
      </div>
    </div>
  )
}

const LoadingState = () => {
  return (
    <div className="text-center py-8">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
      <h2 className="text-xl font-semibold text-gray-800 mb-2">
        Processing OAuth...
      </h2>
      <p className="text-gray-600">
        Please wait while we connect to your Jira workspace.
      </p>
    </div>
  )
}

export default function JiraOAuthPage() {
  const router = useRouter()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [callbackData, setCallbackData] = useState<CallbackData>({})

  useEffect(() => {
    const processCallback = async () => {
      try {
        const urlParams = new URLSearchParams(window.location.search)
        const success = urlParams.get('success') === 'true'
        const error = urlParams.get('error')
        const workspace = urlParams.get('workspace')

        setCallbackData({ success, error, workspace })
        setStatus(success ? 'success' : 'error')

        if (success) {
          // Redirect after delay
          setTimeout(() => {
            router.push('/integrations/jira?success=true')
          }, 3000)
        }
      } catch (err) {
        console.error('Error processing OAuth callback:', err)
        setCallbackData({ success: false, error: 'Unknown error occurred' })
        setStatus('error')
      }
    }

    processCallback()
  }, [router])

  const handleClose = () => {
    if (window.opener) {
      window.opener.postMessage({ type: 'jira-oauth-complete', data: callbackData }, '*')
      window.close()
    } else {
      router.push('/integrations/jira')
    }
  }

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingState />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full mx-auto p-6 bg-white rounded-lg shadow-lg">
        <CallbackStatus
          success={status === 'success'}
          workspace={callbackData.workspace}
          onClose={handleClose}
        />
      </div>
    </div>
  )
}
