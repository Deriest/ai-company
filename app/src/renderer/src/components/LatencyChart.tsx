/** @license MIT License (c) AI Company 2024 */

import { useEffect, useState } from 'react';
import { Card, PageHeader } from './kit';

interface LatencyStats {
  tier: string;
  avg_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  sample_count: number;
}

export function LatencyChart() {
  const [data, setData] = useState<LatencyStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLatencyData = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/latency/stats?days=7');
      if (!response.ok) throw new Error('Failed to fetch latency data');
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatencyData();
    const interval = setInterval(fetchLatencyData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Card className="w-full">
        <PageHeader title="Latency Performance by Tier" />
        <div className="p-6 text-center text-muted-foreground">Loading...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full border-destructive/40 bg-destructive/5">
        <PageHeader title="Latency Performance by Tier" />
        <div className="p-6 text-center text-destructive">Error: {error}</div>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card className="w-full">
        <PageHeader title="Latency Performance by Tier" />
        <div className="p-6 text-center text-muted-foreground">No latency data available yet</div>
      </Card>
    );
  }

  const tiers = data.map(d => d.tier);
  const maxAvg = Math.max(...data.map(d => d.avg_latency_ms));
  const chartHeight = 250;
  const barWidth = Math.min(80, Math.max(40, 180 / tiers.length - 8));
  
  const totalSamples = data.reduce((sum, d) => sum + d.sample_count, 0);

  return (
    <Card className="w-full">
      <PageHeader 
        title="Latency Performance by Model Tier"
        subtitle={`Last 7 days • ${totalSamples} total requests`}
      />
      <div className="px-6 pb-6">
        <div className="flex items-end justify-center gap-8 h-[250px]">
          {data.map((stat, index) => {
            const avgHeight = maxAvg > 0 ? (stat.avg_latency_ms / maxAvg) * chartHeight : 0;
            const maxHeight = maxAvg > 0 ? (stat.max_latency_ms / maxAvg) * chartHeight : 0;
            
            return (
              <div key={stat.tier} className="flex flex-col items-center group relative">
                {/* Tooltip on hover */}
                <div className="absolute bottom-full mb-2 opacity-0 group-hover:opacity-100 transition-opacity bg-card border rounded p-3 text-sm shadow-lg z-10 whitespace-nowrap max-w-[200px]">
                  <strong className="block mb-1">{stat.tier}</strong>
                  Avg: {stat.avg_latency_ms}ms<br />
                  Min: {stat.min_latency_ms}ms<br />
                  Max: {stat.max_latency_ms}ms<br />
                  Samples: {stat.sample_count}
                </div>
                
                {/* Bars */}
                <div className="flex flex-col items-center gap-1">
                  <div 
                    className="rounded-t bg-accent"
                    style={{ height: `${maxHeight}px`, width: `${barWidth}px` }}
                    title={`Max: ${stat.max_latency_ms}ms`}
                  />
                  <div 
                    className="rounded-b bg-primary"
                    style={{ height: `${avgHeight}px`, width: `${barWidth}px` }}
                    title={`Avg: ${stat.avg_latency_ms}ms`}
                  />
                </div>
                
                {/* Label */}
                <div className="mt-4 text-xs font-medium text-center w-max break-all px-2">
                  {stat.tier}
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Legend */}
        <div className="flex justify-center gap-8 mt-6 pt-4 border-t">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-primary rounded" />
            <span className="text-sm text-muted-foreground">Average Latency</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-accent rounded" />
            <span className="text-sm text-muted-foreground">Max Latency</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
