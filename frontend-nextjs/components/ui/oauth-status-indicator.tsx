import React from 'react'
import { CheckCircle, XCircle, Clock, RefreshCw, Shield, ShieldX } from 'lucide-react'

interface OAuthStatusIndicatorProps {/* TODO: Fix missing expression */}
}

interface StatusInfoProps {/* TODO: Fix missing expression */}
}

const StatusInfo: React.FC<StatusInfoProps> = ({ status, message, color, icon }) => {/* TODO: Fix missing expression */}
    <div className={`flex items-center space-x-3 p-4 rounded-lg border ${color}`}>
      {icon}
      <div>
        <h3 className='text-lg font-semibold'>{status}</h3>
        <p className='text-sm text-gray-600'>{message}</p>
      </div>
    </div>
  )
}

export const OAuthStatusIndicator: React.FC<OAuthStatusIndicatorProps> = ({/* TODO: Fix missing expression */})
  isLoading = false}) => {/* TODO: Fix missing expression */}
          icon: <CheckCircle className='h-6 w-6 text-green-600' />}
      case 'disconnected':
        return {/* TODO: Fix missing expression */}
          icon: <XCircle className='h-6 w-6 text-red-600' />}
      case 'pending':
        return {/* TODO: Fix missing expression */}
          icon: <Clock className='h-6 w-6 text-yellow-600' />}
      default: return {/* TODO: Fix missing expression */}
          icon: <ShieldX className='h-6 w-6 text-gray-600' />}
    }
  }

  const statusInfo = getStatusInfo(oauthStatus);

  return (
    <div className='space-y-6'>
      <StatusInfo
        status={statusInfo.status}
        message={statusInfo.message}
        color={statusInfo.color}
        icon={statusInfo.icon}
      />

      <div className='flex flex-wrap gap-3'>
        {/* TODO: Fix missing expression */}
            onClick={onRefresh}
            disabled={isLoading}
            className='flex items-center space-x-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed'
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>)
        )}

        {/* TODO: Fix missing expression */}
            onClick={onRevoke}
            className='flex items-center space-x-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600'
          >
            <ShieldX className='h-4 w-4' />
            <span>Revoke</span>
          </button>
        )}

        {/* TODO: Fix missing expression */}
            onClick={onSwitch}
            className='flex items-center space-x-2 px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600'
          >
            <Shield className='h-4 w-4' />
            <span>Switch Account</span>
          </button>
        )}
      </div>
    </div>
  )
}
