'use client';

import { useState } from 'react';
import { ChevronDownIcon, CheckIcon } from 'lucide-react';

interface Asset {
  symbol: string;
  name: string;
  type: string;
}

interface AssetSelectorProps {
  assets: Asset[];
  selectedAsset: string;
  onAssetChange: (symbol: string) => void;
}

export default function AssetSelector({ assets, selectedAsset, onAssetChange }: AssetSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const selectedAssetData = assets.find(asset => asset.symbol === selectedAsset);

  return (
    <div className="w-full max-w-md">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Select Asset for Analysis
      </label>
      <div className="relative">
        <button
          type="button"
          className="relative w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-sm pl-3 pr-10 py-3 text-left cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                <span className="text-sm font-semibold text-blue-800 dark:text-blue-200">
                  {selectedAsset.slice(0, 2)}
                </span>
              </div>
            </div>
            <div className="ml-3">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                {selectedAsset}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {selectedAssetData?.name || 'Unknown Asset'}
              </div>
            </div>
          </div>
          <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
            <ChevronDownIcon
              className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${
                isOpen ? 'transform rotate-180' : ''
              }`}
            />
          </span>
        </button>

        {isOpen && (
          <div className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-800 shadow-lg max-h-96 rounded-lg py-1 text-base border border-gray-300 dark:border-gray-600 overflow-auto focus:outline-none">
            {/* Group assets by type */}
            {['forex', 'crypto'].map((type) => {
              const typeAssets = assets.filter(a => a.type === type);
              if (typeAssets.length === 0) return null;
              
              return (
                <div key={type}>
                  <div className="px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide bg-gray-50 dark:bg-gray-750">
                    {type === 'forex' ? '💱 Forex (Level 2 Data)' : '₿ Cryptocurrency'}
                  </div>
                  {typeAssets.map((asset) => (
                    <div
                      key={asset.symbol}
                      className={`cursor-pointer select-none relative py-3 pl-3 pr-9 hover:bg-gray-50 dark:hover:bg-gray-700 ${
                        selectedAsset === asset.symbol ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                      }`}
                      onClick={() => {
                        onAssetChange(asset.symbol);
                        setIsOpen(false);
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="flex-shrink-0">
                            <div className={`w-6 h-6 ${type === 'forex' ? 'bg-purple-100 dark:bg-purple-900' : 'bg-blue-100 dark:bg-blue-900'} rounded-full flex items-center justify-center`}>
                              <span className={`text-xs font-semibold ${type === 'forex' ? 'text-purple-800 dark:text-purple-200' : 'text-blue-800 dark:text-blue-200'}`}>
                                {asset.symbol.slice(0, 2)}
                              </span>
                            </div>
                          </div>
                          <div className="ml-3">
                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                              {asset.symbol}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                              {asset.name}
                            </div>
                          </div>
                        </div>
                        {selectedAsset === asset.symbol && (
                          <CheckIcon className="h-5 w-5 text-blue-600 mr-2" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
