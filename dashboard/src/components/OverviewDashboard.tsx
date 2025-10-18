'use client';

import { useState, useEffect } from 'react';
import { TrendingUpIcon, TrendingDownIcon, ActivityIcon, DollarSignIcon, RefreshCwIcon, AlertCircleIcon, ClockIcon, TimerIcon, ZapIcon } from 'lucide-react';
import { API_ENDPOINTS } from '@/lib/config';

interface MicrostructureData {
  symbol: string;
  timestamp: string;
  features: {
    ofi: number;
    spread_bps: number;
    aggressive_ratio: number;
    realized_vol: number;
    current_price: number;
    trade_count: number;
    depth_imbalance: number;
    liquidity_concentration: number;
    data_type?: string;
    asset_type?: string;
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
  timing?: {
    expected_tp_minutes: number;
    expected_sl_minutes: number;
    recommended_hold_min: number;
    recommended_hold_max: number;
    signal_valid_minutes: number;
    analysis_window_trades: number;
    data_window_seconds: number;
    data_window_minutes: number;
    suggested_timeframe: string;
    data_freshness: string;
  };
}

interface OverviewDashboardProps {
  symbol: string;
}

export default function OverviewDashboard({ symbol }: OverviewDashboardProps) {
  const [data, setData] = useState<MicrostructureData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchData = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.microstructure(symbol));
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
    // Refresh every 5 minutes instead of 30 seconds
    const interval = setInterval(fetchData, 300000);  // 5 minutes
    return () => clearInterval(interval);
  }, [symbol]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-4"></div>
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
        <AlertCircleIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500 dark:text-gray-400">No data available for {symbol}</p>
      </div>
    );
  }

  const getBiasColor = (bias: string) => {
    switch (bias) {
      case 'long': return 'text-green-600 dark:text-green-400';
      case 'short': return 'text-red-600 dark:text-red-400';
      default: return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getBiasIcon = (bias: string) => {
    return bias === 'long' ? TrendingUpIcon : bias === 'short' ? TrendingDownIcon : ActivityIcon;
  };

  const formatCurrency = (num: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(num);
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };
  
  const formatTime = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  };
  
  const getTimeframeColor = (timeframe: string) => {
    switch (timeframe) {
      case 'scalp': return 'from-red-500 to-orange-500';
      case 'intraday': return 'from-blue-500 to-indigo-500';
      case 'swing': return 'from-purple-500 to-pink-500';
      default: return 'from-gray-500 to-gray-600';
    }
  };
  
  const getTimeframeLabel = (timeframe: string) => {
    switch (timeframe) {
      case 'scalp': return '⚡ Scalp';
      case 'intraday': return '📊 Intraday';
      case 'swing': return '📈 Swing';
      default: return '📉 Trade';
    }
  };
  
  // Calculate signal age
  const signalAge = data.timestamp ? Math.floor((new Date().getTime() - new Date(data.timestamp).getTime()) / 1000 / 60) : 0;
  const isSignalFresh = signalAge < 5;  // Fresh if < 5 minutes old

  const BiasIcon = getBiasIcon(data.scenario.bias);

  return (
    <div className="space-y-6">
      {/* Signal Freshness Alert */}
      {!isSignalFresh && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 flex items-center space-x-3">
          <AlertCircleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
          <div>
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              Signal is {signalAge} minutes old - Consider refreshing for latest analysis
            </p>
          </div>
        </div>
      )}
      
      {/* Top Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Price Card */}
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-blue-100 text-sm font-medium">Current Price</span>
            <div className="flex items-center space-x-2">
              {data.timing?.data_freshness === 'live' && (
                <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
              )}
              <DollarSignIcon className="w-5 h-5 text-blue-200" />
            </div>
          </div>
          <div className="text-3xl font-bold">{formatCurrency(data.features.current_price)}</div>
          <div className="text-blue-100 text-sm mt-2">
            {data.features.trade_count} trades
            {data.timing?.data_window_seconds > 0 && (
              <span className="ml-1">
                • {data.timing.data_window_seconds < 60 
                  ? `${data.timing.data_window_seconds}s` 
                  : `${data.timing.data_window_minutes}m`} span
              </span>
            )}
          </div>
        </div>

        {/* Trading Bias Card */}
        <div className={`bg-gradient-to-br ${data.scenario.bias === 'long' ? 'from-green-500 to-green-600' : data.scenario.bias === 'short' ? 'from-red-500 to-red-600' : 'from-gray-500 to-gray-600'} rounded-xl shadow-lg p-6 text-white`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/80 text-sm font-medium">Trading Bias</span>
            <BiasIcon className="w-5 h-5 text-white/80" />
          </div>
          <div className="text-3xl font-bold capitalize">{data.scenario.bias}</div>
          <div className="text-white/80 text-sm mt-2">{formatPercent(data.scenario.confidence)} confidence</div>
        </div>

        {/* OFI Card */}
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-purple-100 text-sm font-medium">Order Flow</span>
            <ActivityIcon className="w-5 h-5 text-purple-200" />
          </div>
          <div className="text-3xl font-bold">{data.features.ofi.toFixed(3)}</div>
          <div className="text-purple-100 text-sm mt-2">
            {data.features.ofi > 0 ? 'Buy pressure' : data.features.ofi < 0 ? 'Sell pressure' : 'Neutral'}
          </div>
        </div>

        {/* Volatility Card */}
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl shadow-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-orange-100 text-sm font-medium">Volatility</span>
            <ActivityIcon className="w-5 h-5 text-orange-200" />
          </div>
          <div className="text-3xl font-bold">{formatPercent(data.features.realized_vol)}</div>
          <div className="text-orange-100 text-sm mt-2 capitalize">{data.scenario.risk_regime.replace('_', ' ')}</div>
        </div>
      </div>

      {/* Timing & Timeframe Card */}
      {data.timing && (
        <div className={`bg-gradient-to-r ${getTimeframeColor(data.timing.suggested_timeframe)} rounded-xl shadow-lg p-6 text-white`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <TimerIcon className="w-6 h-6" />
              <h3 className="text-xl font-bold">{getTimeframeLabel(data.timing.suggested_timeframe)} Trade</h3>
            </div>
            <div className={`px-3 py-1 rounded-full text-xs font-medium ${isSignalFresh ? 'bg-green-400/30 text-white' : 'bg-yellow-400/30 text-white'}`}>
              {isSignalFresh ? '🟢 Fresh' : '🟡 Refresh Soon'}
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-white/70 mb-1">Expected TP</div>
              <div className="text-lg font-bold">{formatTime(data.timing.expected_tp_minutes)}</div>
            </div>
            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-white/70 mb-1">Hold Period</div>
              <div className="text-lg font-bold">{formatTime(data.timing.recommended_hold_min)}-{formatTime(data.timing.recommended_hold_max)}</div>
            </div>
            <div className="bg-white/10 rounded-lg p-3">
              <div className="text-xs text-white/70 mb-1">Refresh In</div>
              <div className="text-lg font-bold">5min</div>
            </div>
          </div>
          
          <div className="mt-4 text-sm text-white/80">
            💡 <strong>Strategy:</strong> Review signal • Execute trade • Monitor for {formatTime(data.timing.recommended_hold_max)} • Exit if OFI flips or time reached
          </div>
        </div>
      )}

      {/* Trading Scenario Card */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Trading Levels</h3>
          <button
            onClick={fetchData}
            className="flex items-center space-x-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
          >
            <RefreshCwIcon className="w-4 h-4" />
            <span className="text-sm font-medium">Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Entry */}
          <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Entry Price</div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {formatCurrency(data.scenario.recommended.entry)}
            </div>
          </div>

          {/* Take Profit */}
          <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Take Profit</div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatCurrency(data.scenario.recommended.tp)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {formatPercent(data.monte_carlo.tp_hit_prob)} probability
              {data.timing && <span className="ml-1">• ~{formatTime(data.timing.expected_tp_minutes)}</span>}
            </div>
          </div>

          {/* Stop Loss */}
          <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Stop Loss</div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formatCurrency(data.scenario.recommended.sl)}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {formatPercent(data.monte_carlo.sl_hit_prob)} probability
              {data.timing && <span className="ml-1">• ~{formatTime(data.timing.expected_sl_minutes)}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Spread</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            {data.features.spread_bps.toFixed(2)} bps
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Aggressive Ratio</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            {formatPercent(data.features.aggressive_ratio)}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Depth Imbalance</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            {data.features.depth_imbalance.toFixed(3)}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">Liquidity</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            {formatPercent(data.features.liquidity_concentration)}
          </div>
        </div>
      </div>

      {/* Exit Signal Monitor */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6">
        <div className="flex items-start space-x-3">
          <ZapIcon className="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">Exit Signal Watch</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-600 dark:text-gray-400">OFI Flip:</span>
                <span className={`ml-2 font-medium ${data.features.ofi > 0 ? 'text-green-600' : data.features.ofi < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {data.features.ofi > 0 ? '✓ Bullish' : data.features.ofi < 0 ? '✓ Bearish' : '⚠ Neutral'}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Liquidity:</span>
                <span className={`ml-2 font-medium ${data.features.liquidity_concentration > 0.99 ? 'text-green-600' : 'text-amber-600'}`}>
                  {data.features.liquidity_concentration > 0.99 ? '✓ Good' : '⚠ Watch'}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Signal Age:</span>
                <span className={`ml-2 font-medium ${isSignalFresh ? 'text-green-600' : 'text-amber-600'}`}>
                  {signalAge}m {isSignalFresh ? '✓' : '⚠'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Data Flow & Last Update */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${data.timing?.data_freshness === 'live' ? 'bg-green-500 animate-pulse' : 'bg-blue-500'}`}></div>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {data.timing?.data_freshness === 'live' ? '🟢 Live Data' : '🔵 Recent Data'}
              </span>
            </div>
            
            {data.timing && (
              <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
                <div>
                  <span className="font-medium text-gray-900 dark:text-white">{data.timing.analysis_window_trades}</span>
                  <span className="ml-1">{data.features.asset_type === 'forex' ? 'quotes' : 'trades'}</span>
                </div>
                {data.timing.data_window_seconds > 0 && (
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {data.timing.data_window_seconds < 60 
                        ? `${data.timing.data_window_seconds}s`
                        : data.timing.data_window_minutes < 60
                        ? `${data.timing.data_window_minutes}m`
                        : `${Math.floor(data.timing.data_window_minutes / 60)}h ${data.timing.data_window_minutes % 60}m`
                      }
                    </span>
                    <span className="ml-1">data span</span>
                  </div>
                )}
                {data.features.data_type === 'level2' && (
                  <div className="flex items-center space-x-1">
                    <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    <span className="font-medium text-blue-600 dark:text-blue-400">Level 2</span>
                  </div>
                )}
              </div>
            )}
          </div>
          
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Updated: {lastUpdate.toLocaleTimeString()} • Auto-refresh: 5min
          </div>
        </div>
      </div>
    </div>
  );
}

