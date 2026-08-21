/** @license MIT License (c) AI Company 2024 */

import { LatencyChart } from './LatencyChart';

export function PerformanceInsights() {
  return (
    <div className="flex-1 overflow-auto bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Performance Insights
        </h1>
        
        <p className="text-muted-foreground">
          Monitor response latency across model tiers to identify performance patterns and optimize selection.
        </p>
        
        <div className="space-y-6">
          <LatencyChart />
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-lg border bg-card p-6 shadow-sm">
              <h3 className="font-semibold mb-3 text-foreground">How to Read This Chart</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary mt-1.5 flex-shrink-0" />
                  <span><strong>Average (blue)</strong>: Typical response time for each tier</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full bg-accent mt-1.5 flex-shrink-0" />
                  <span><strong>Maximum (teal)</strong>: Peak response times observed</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full bg-foreground mt-1.5 flex-shrink-0" />
                  <span><strong>Hover tooltip</strong>: Shows detailed min/max/avg/sample counts</span>
                </li>
              </ul>
            </div>
            
            <div className="rounded-lg border bg-card p-6 shadow-sm">
              <h3 className="font-semibold mb-3 text-foreground">Tips for Better Performance</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-1 mr-2">✓</span>
                  <span>Use lower-tier models for simple tasks when latency matters</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-1 mr-2">✓</span>
                  <span>Premium tiers may have higher baseline but better consistency</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500 mt-1 mr-2">✓</span>
                  <span>Data refreshes automatically every 30 seconds</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
