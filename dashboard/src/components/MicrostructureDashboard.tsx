'use client';

import { useState, useEffect } from 'react';
import { TrendingUpIcon, TrendingDownIcon, ActivityIcon, BarChart3Icon, RefreshCwIcon } from 'lucide-react';

interface MicrostructureData {
  symbol: string;
  timestamp: string;
  features: {
    ofi: number;
    ofi_mean: number;
    ofi_std: number;
    spread_current: number;
    spread_mean: number;
    spread_bps: number;
    aggressive_ratio: number;
    passive_ratio: number;
    quadratic_variation: number;
    realized_vol: number;
    current_price: number;
    trade_count: number;
    // Advanced metrics
    depth_imbalance: number;
    liquidity_concentration: number;
    microprice: number;
    price_impact_lambda: number;
    market_depth_elasticity: number;
    effective_spread: number;
    effective_spread_bps: number;
  };
  scenario: {
    bias: string;
    confidence: number;
    risk_regime: string;
    recommended: {
      entry: number;
      tp: number;
      sl: number;
    };
  };
  monte_carlo: {
    upside_prob: number;
    downside_prob: number;
    tp_hit_prob: number;
    sl_hit_prob: number;
    var_5pct: number;
  };
  orderbook: {
    bids: Array<{price: number, size: number}>;
    asks: Array<{price: number, size: number}>;
    best_bid: number;
    best_ask: number;
    mid_price: number;
    spread: number;
    spread_bps: number;
  } | null;
}

interface MicrostructureDashboardProps {
  symbol: string;
}

export default function MicrostructureDashboard({ symbol }: MicrostructureDashboardProps) {
  const [data, setData] = useState<MicrostructureData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchData = async () => {
    try {
      const response = await fetch(`http://localhost:8000/microstructure/${symbol}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      setData(result);
      setLastUpdate(new Date());
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching microstructure data:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchData, 300000);
    return () => clearInterval(interval);
  }, [symbol]);

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          No data available for {symbol}
        </div>
      </div>
    );
  }

  const formatNumber = (num: number, decimals: number = 4) => {
    return num.toFixed(decimals);
  };

  const formatPercentage = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const getBiasColor = (bias: string) => {
    switch (bias) {
      case 'long': return 'text-green-600 dark:text-green-400';
      case 'short': return 'text-red-600 dark:text-red-400';
      default: return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getRiskRegimeColor = (regime: string) => {
    switch (regime) {
      case 'low_vol': return 'text-green-600 dark:text-green-400';
      case 'high_vol': return 'text-red-600 dark:text-red-400';
      default: return 'text-yellow-600 dark:text-yellow-400';
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <ActivityIcon className="h-6 w-6 text-blue-600" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Microstructure Analysis - {symbol}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Last updated: {lastUpdate.toLocaleTimeString()}
              </p>
            </div>
          </div>
          <button
            onClick={fetchData}
            className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <RefreshCwIcon className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {/* Trading Scenario */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">Trading Scenario</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600 dark:text-gray-400">Bias</span>
              <span className={`text-sm font-semibold capitalize ${getBiasColor(data.scenario.bias)}`}>
                {data.scenario.bias}
              </span>
            </div>
            <div className="mt-2">
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatPercentage(data.scenario.confidence)}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Confidence</div>
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600 dark:text-gray-400">Risk Regime</span>
              <span className={`text-sm font-semibold capitalize ${getRiskRegimeColor(data.scenario.risk_regime)}`}>
                {data.scenario.risk_regime.replace('_', ' ')}
              </span>
            </div>
          </div>

          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Recommended Levels</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Entry:</span>
                <span className="font-mono text-gray-900 dark:text-white">${formatNumber(data.scenario.recommended.entry)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-green-600 dark:text-green-400">TP:</span>
                <span className="font-mono text-green-600 dark:text-green-400">${formatNumber(data.scenario.recommended.tp)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-600 dark:text-red-400">SL:</span>
                <span className="font-mono text-red-600 dark:text-red-400">${formatNumber(data.scenario.recommended.sl)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">Key Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {formatNumber(data.features.ofi, 3)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">OFI</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              ${formatNumber(data.features.spread_current)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Spread</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {data.features.spread_bps.toFixed(2)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Spread (bps)</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatPercentage(data.features.aggressive_ratio)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Aggressive</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {formatPercentage(data.features.passive_ratio)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Passive</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {formatPercentage(data.features.realized_vol)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Volatility</div>
          </div>

          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {(data.features.quadratic_variation * 10000).toFixed(4)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">QV (×10⁴)</div>
          </div>
        </div>
      </div>

      {/* Advanced Microstructure Metrics */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">Advanced Microstructure Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="text-center">
            <div className="text-xl font-bold text-blue-600 dark:text-blue-400">
              {formatNumber(data.features.depth_imbalance, 3)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Depth Imbalance</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Liquidity bias</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-green-600 dark:text-green-400">
              {formatPercentage(data.features.liquidity_concentration)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Liquidity Concentration</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Top-5% depth</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-purple-600 dark:text-purple-400">
              ${formatNumber(data.features.microprice, 2)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Microprice</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Fair value</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-orange-600 dark:text-orange-400">
              ${formatNumber(data.features.price_impact_lambda, 2)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Price Impact (λ)</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Per trade</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-red-600 dark:text-red-400">
              {(data.features.market_depth_elasticity * 100).toFixed(2)}%
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Depth Elasticity</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Per $1M</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400">
              {data.features.effective_spread_bps.toFixed(2)} bps
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Effective Spread</div>
            <div className="text-xs text-gray-400 dark:text-gray-500">Execution cost</div>
          </div>
        </div>
      </div>

      {/* Monte Carlo Probabilities */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">Monte Carlo Analysis</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xl font-bold text-green-600 dark:text-green-400">
              {formatPercentage(data.monte_carlo.tp_hit_prob)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">TP Hit Prob</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-red-600 dark:text-red-400">
              {formatPercentage(data.monte_carlo.sl_hit_prob)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">SL Hit Prob</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-blue-600 dark:text-blue-400">
              {formatPercentage(data.monte_carlo.upside_prob)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Upside Prob</div>
          </div>

          <div className="text-center">
            <div className="text-xl font-bold text-gray-900 dark:text-white">
              ${formatNumber(data.monte_carlo.var_5pct)}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">VaR (5%)</div>
          </div>
        </div>
      </div>

      {/* Order Book */}
      {data.orderbook && (
        <div className="px-6 py-4">
          <h3 className="text-md font-medium text-gray-900 dark:text-white mb-3">Order Book</h3>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Bids */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Bids</h4>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {data.orderbook.bids.slice(0, 10).map((bid, index) => (
                  <div key={index} className="flex justify-between text-sm bg-green-50 dark:bg-green-900/20 p-2 rounded">
                    <span className="font-mono text-green-700 dark:text-green-300">${formatNumber(bid.price)}</span>
                    <span className="text-green-600 dark:text-green-400">{formatNumber(bid.size, 2)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Best Bid/Ask */}
            <div className="text-center">
              <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Best Levels</div>
              <div className="space-y-2">
                <div className="text-lg font-semibold text-green-600 dark:text-green-400">
                  ${formatNumber(data.orderbook.best_bid || 0)}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Best Bid</div>
                <div className="text-lg font-semibold text-red-600 dark:text-red-400">
                  ${formatNumber(data.orderbook.best_ask || 0)}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Best Ask</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  ${formatNumber(data.orderbook.mid_price || 0)}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">Mid Price</div>
              </div>
            </div>

            {/* Asks */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Asks</h4>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {data.orderbook.asks.slice(0, 10).map((ask, index) => (
                  <div key={index} className="flex justify-between text-sm bg-red-50 dark:bg-red-900/20 p-2 rounded">
                    <span className="font-mono text-red-700 dark:text-red-300">${formatNumber(ask.price)}</span>
                    <span className="text-red-600 dark:text-red-400">{formatNumber(ask.size, 2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
