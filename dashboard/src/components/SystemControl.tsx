'use client';

import { useState, useEffect } from 'react';
import { PowerIcon, WifiIcon, WifiOffIcon, RefreshCwIcon, AlertCircleIcon, CheckCircleIcon } from 'lucide-react';
import { API_ENDPOINTS } from '@/lib/config';

interface SystemStatus {
  api_online: boolean;
  data_feed_active: boolean;
  last_check: string;
}

export default function SystemControl() {
  const [status, setStatus] = useState<SystemStatus>({ api_online: false, data_feed_active: false, last_check: '' });
  const [checking, setChecking] = useState(false);

  const checkStatus = async () => {
    setChecking(true);
    try {
      // Check API health
      const response = await fetch(API_ENDPOINTS.health);
      if (response.ok) {
        setStatus({
          api_online: true,
          data_feed_active: true,
          last_check: new Date().toISOString()
        });
      }
    } catch (error) {
      setStatus({
        api_online: false,
        data_feed_active: false,
        last_check: new Date().toISOString()
      });
    }
    setChecking(false);
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 10000); // Check every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between">
        {/* Status Indicators */}
        <div className="flex items-center space-x-6">
          {/* API Status */}
          <div className="flex items-center space-x-2">
            {status.api_online ? (
              <>
                <CheckCircleIcon className="w-5 h-5 text-green-500" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">API Connected</span>
              </>
            ) : (
              <>
                <AlertCircleIcon className="w-5 h-5 text-red-500" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">API Offline</span>
              </>
            )}
          </div>

          {/* Data Feed Status */}
          <div className="flex items-center space-x-2">
            {status.data_feed_active ? (
              <>
                <WifiIcon className="w-5 h-5 text-green-500" />
                <span className="text-sm font-medium text-gray-900 dark:text-white">Live Data</span>
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              </>
            ) : (
              <>
                <WifiOffIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm font-medium text-gray-500 dark:text-gray-400">No Data Feed</span>
              </>
            )}
          </div>
        </div>

        {/* Control Button */}
        <button
          onClick={checkStatus}
          disabled={checking}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white rounded-lg transition-colors text-sm font-medium"
        >
          <RefreshCwIcon className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
          <span>{checking ? 'Checking...' : 'Refresh Status'}</span>
        </button>
      </div>

      {/* Connection Instructions */}
      {!status.api_online && (
        <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <p className="text-sm text-yellow-800 dark:text-yellow-200 font-medium mb-2">
            ⚠️ API Server Not Running
          </p>
          <p className="text-xs text-yellow-700 dark:text-yellow-300 mb-2">
            To start the dashboard, open a terminal and run:
          </p>
          <code className="block text-xs bg-gray-900 text-green-400 p-2 rounded font-mono">
            ./start_all.sh
          </code>
          <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
            Or manually start the API: <code className="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">uvicorn src.api.server:app --port 8000</code>
          </p>
        </div>
      )}
    </div>
  );
}

