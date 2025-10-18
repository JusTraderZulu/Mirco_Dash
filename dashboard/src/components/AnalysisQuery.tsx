'use client';

import { useState } from 'react';
import { SendIcon, BotIcon, UserIcon, LoaderIcon } from 'lucide-react';
import { API_ENDPOINTS } from '@/lib/config';

interface AnalysisQueryProps {
  symbol: string;
}

interface AnalysisResponse {
  query: string;
  symbol: string;
  timestamp: string;
  analysis: string;
  features: Record<string, number>;
  recommendations: string[];
}

export default function AnalysisQuery({ symbol }: AnalysisQueryProps) {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(API_ENDPOINTS.analysis, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          symbol: symbol,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const sampleQueries = [
    `What does the current microstructure suggest for ${symbol}?`,
    `Should I go long or short on ${symbol} based on the order flow?`,
    `What are the key risk factors I should consider for ${symbol}?`,
    `How is the spread and liquidity looking for ${symbol}?`,
  ];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-3">
          <BotIcon className="h-6 w-6 text-purple-600" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              AI Analysis Assistant
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Ask questions about {symbol} microstructure and get AI-powered insights
            </p>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Query Input */}
        <form onSubmit={handleSubmit} className="mb-6">
          <div className="flex space-x-3">
            <div className="flex-1">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Ask me anything about ${symbol}'s microstructure...`}
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg shadow-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none dark:bg-gray-700 dark:text-white"
                rows={3}
                disabled={isLoading}
              />
            </div>
            <div className="flex-shrink-0">
              <button
                type="submit"
                disabled={!query.trim() || isLoading}
                className="h-full px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-lg font-medium focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:cursor-not-allowed flex items-center"
              >
                {isLoading ? (
                  <LoaderIcon className="h-5 w-5 animate-spin" />
                ) : (
                  <SendIcon className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Sample Queries */}
        <div className="mb-6">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">Try these sample questions:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {sampleQueries.map((sampleQuery, index) => (
              <button
                key={index}
                onClick={() => setQuery(sampleQuery)}
                className="text-left px-3 py-2 text-sm bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg border border-gray-200 dark:border-gray-600 transition-colors"
              >
                {sampleQuery}
              </button>
            ))}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-center space-x-2">
              <div className="text-red-600 dark:text-red-400">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          </div>
        )}

        {/* Response Display */}
        {response && (
          <div className="space-y-4">
            {/* User Query */}
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                  <UserIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
              <div className="flex-1">
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                  <p className="text-sm text-blue-900 dark:text-blue-100">
                    {response.query}
                  </p>
                </div>
              </div>
            </div>

            {/* AI Response */}
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center">
                  <BotIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
              <div className="flex-1">
                <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <p className="text-gray-900 dark:text-gray-100 whitespace-pre-wrap">
                      {response.analysis}
                    </p>

                    {/* Key Features */}
                    {Object.keys(response.features).length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
                          Current Market Features:
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                          {Object.entries(response.features).map(([key, value]) => (
                            <div key={key} className="bg-white dark:bg-gray-800 p-2 rounded border">
                              <span className="font-medium text-gray-700 dark:text-gray-300">
                                {key.replace('_', ' ').toUpperCase()}:
                              </span>
                              <span className="ml-1 text-gray-900 dark:text-gray-100">
                                {typeof value === 'number' ? value.toFixed(4) : value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {response.recommendations.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
                          Key Recommendations:
                        </h4>
                        <ul className="space-y-1">
                          {response.recommendations.map((rec, index) => (
                            <li key={index} className="text-sm text-gray-700 dark:text-gray-300 flex items-start">
                              <span className="text-purple-600 dark:text-purple-400 mr-2">•</span>
                              {rec}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        {!response && !isLoading && (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <BotIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-sm">
              Ask me questions about {symbol}'s microstructure, trading signals, or market analysis.
            </p>
            <p className="text-xs mt-2">
              I can help interpret OFI, spread dynamics, risk metrics, and trading scenarios.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
