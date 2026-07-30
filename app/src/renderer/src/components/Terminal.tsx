import { useEffect, useRef, useState } from 'react'
import { Terminal as TerminalIcon, X } from 'lucide-react'

export function TerminalPanel({ cwd, onClose }: { cwd?: string; onClose: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [output, setOutput] = useState<string[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    window.aic?.termStart?.(cwd)
    const off = window.aic?.onTermData?.((data: string) => {
      setOutput(prev => [...prev.slice(-500), data])
    })
    return () => {
      off?.()
      window.aic?.termKill?.()
    }
  }, [cwd])

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [output])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      const cmd = (e.target as HTMLInputElement).value
      window.aic?.termWrite?.(cmd + '\n')
      ;(e.target as HTMLInputElement).value = ''
    }
  }

  return (
    <div className="flex flex-col border-t border-border bg-[oklch(0.10_0.005_250)]" style={{ height: 240 }}>
      <div className="flex items-center justify-between px-3 py-1 border-b border-border/50">
        <div className="flex items-center gap-2">
          <TerminalIcon className="size-3 text-muted-foreground" />
          <span className="text-[10px] font-medium text-muted-foreground">Terminal</span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-3" />
        </button>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto scroll-thin p-2 font-mono text-[11px] text-foreground/80">
        <pre className="whitespace-pre-wrap">{output.join('')}</pre>
      </div>
      <div className="border-t border-border/50 px-2 py-1">
        <input
          ref={inputRef}
          onKeyDown={handleKeyDown}
          placeholder="$ command..."
          className="w-full bg-transparent font-mono text-[11px] outline-none placeholder:text-muted-foreground/40"
          autoFocus
        />
      </div>
    </div>
  )
}
