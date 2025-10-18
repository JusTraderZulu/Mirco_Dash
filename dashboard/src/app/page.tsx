'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { LayoutDashboard, TrendingUp, MessageSquare, Settings } from 'lucide-react';

// Dynamically import components with no SSR to avoid hydration issues
const AssetSelector = dynamic(() => import('@/components/AssetSelector'), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-gray-200 h-20 rounded"></div>
});

const OverviewDashboard = dynamic(() => import('@/components/OverviewDashboard'), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-gray-200 h-96 rounded"></div>
});

const MicrostructureDashboard = dynamic(() => import('@/components/MicrostructureDashboard'), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-gray-200 h-96 rounded"></div>
});

const AnalysisQuery = dynamic(() => import('@/components/AnalysisQuery'), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-gray-200 h-64 rounded"></div>
});

const SystemControl = dynamic(() => import('@/components/SystemControl'), {
  ssr: false,
  loading: () => <div className="animate-pulse bg-gray-200 h-16 rounded"></div>
});

interface Asset {
  symbol: string;
  name: string;
  type: string;
}

// Default assets - will be replaced by API data
const DEFAULT_ASSETS: Asset[] = [
  // Forex (Level 2 Data)
  { symbol: 'EUR-USD', name: 'EUR/USD', type: 'forex' },
  { symbol: 'GBP-USD', name: 'GBP/USD', type: 'forex' },
  { symbol: 'USD-JPY', name: 'USD/JPY', type: 'forex' },
  { symbol: 'AUD-USD', name: 'AUD/USD', type: 'forex' },
  
  // Crypto (Trade Data)
  { symbol: 'BTC-USD', name: 'Bitcoin', type: 'crypto' },
  { symbol: 'ETH-USD', name: 'Ethereum', type: 'crypto' },
  { symbol: 'SOL-USD', name: 'Solana', type: 'crypto' },
  { symbol: 'DOGE-USD', name: 'Dogecoin', type: 'crypto' },
  { symbol: 'XRP-USD', name: 'Ripple', type: 'crypto' },
  { symbol: 'ADA-USD', name: 'Cardano', type: 'crypto' },
];

type Tab = 'overview' | 'analytics' | 'assistant';

export default function Home() {
  const [selectedAsset, setSelectedAsset] = useState<string>('BTC-USD');
  const [availableAssets, setAvailableAssets] = useState<Asset[]>(DEFAULT_ASSETS);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Fetch available assets on component mount
    const fetchAvailableAssets = async () => {
      try {
        const response = await fetch('http://localhost:8000/assets/available');
        if (!response.ok) {
          console.warn(`API returned ${response.status}, using default assets`);
          return;
        }
        const data = await response.json();
        if (data.assets && data.assets.length > 0) {
          setAvailableAssets(data.assets);
        }
      } catch (error) {
        console.error('Error fetching assets (using defaults):', error);
        // Keep using DEFAULT_ASSETS
      }
    };

    fetchAvailableAssets();
  }, []);

  const handleAssetChange = (symbol: string) => {
    setSelectedAsset(symbol);
  };

  const tabs = [
    { id: 'overview' as Tab, name: 'Overview', icon: LayoutDashboard },
    { id: 'analytics' as Tab, name: 'Advanced Analytics', icon: TrendingUp },
    { id: 'assistant' as Tab, name: 'AI Assistant', icon: MessageSquare },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-lg border-b border-gray-200 dark:border-gray-700 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top Bar */}
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl shadow-lg">
                <TrendingUp className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  TEPM Analytics
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Professional Microstructure Analysis Platform
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2 px-3 py-2 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-green-700 dark:text-green-400">Live</span>
              </div>
              <button className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
                <Settings className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </button>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex space-x-1 border-b border-gray-200 dark:border-gray-700">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center space-x-2 px-4 py-3 font-medium text-sm transition-all
                    ${isActive 
                      ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-blue-50/50 dark:bg-blue-900/20' 
                      : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                    }
                  `}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* System Control Panel */}
        <div className="mb-6">
          <SystemControl />
        </div>

        {/* Asset Selector - Always Visible */}
        <div className="mb-6">
          <AssetSelector
            assets={availableAssets}
            selectedAsset={selectedAsset}
            onAssetChange={handleAssetChange}
          />
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {activeTab === 'overview' && (
            <div className="space-y-6 animate-fadeIn">
              <OverviewDashboard symbol={selectedAsset} />
            </div>
          )}

          {activeTab === 'analytics' && (
            <div className="space-y-6 animate-fadeIn">
              <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl shadow-lg p-6 text-white mb-6">
                <h3 className="text-xl font-bold mb-2">Advanced Microstructure Analytics</h3>
                <p className="text-indigo-100">
                  Deep dive into market microstructure with all metrics: OFI history, spread dynamics, 
                  price impact coefficients, liquidity measures, and Monte Carlo simulations.
                </p>
              </div>
              <MicrostructureDashboard symbol={selectedAsset} />
            </div>
          )}

          {activeTab === 'assistant' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Quick Stats Card */}
              <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
                <h3 className="text-xl font-bold mb-2">AI Trading Assistant</h3>
                <p className="text-blue-100">
                  Ask questions about market conditions, get AI-powered trading insights, 
                  and receive actionable recommendations based on real-time microstructure data.
                </p>
              </div>
              
              <AnalysisQuery symbol={selectedAsset} />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-12 py-6 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-gray-500 dark:text-gray-400">
          <p>TEPM Analytics Dashboard • Real-time Microstructure Analysis • Powered by Polygon & Perplexity AI</p>
        </div>
      </footer>

      <style jsx global>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
