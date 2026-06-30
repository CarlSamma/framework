import { useWebSocket } from '../../hooks/useWebSocket';
import { useEngineStatus } from '../../hooks/useEngineStatus';

export function TopBar() {
  const { connected } = useWebSocket();
  const status = useEngineStatus();

  return (
    <header className="h-12 bg-[var(--bg-card)] border-b border-[var(--bg-border)] flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <span className="font-bold text-[var(--text-primary)] tracking-tight">
          TAP Framework
        </span>
        <span className="text-xs text-[var(--text-muted)] bg-[var(--bg-base)] px-2 py-0.5 rounded-full">
          hybrid
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <span
            className={`w-2 h-2 rounded-full ${
              connected
                ? 'bg-[var(--accent-green)]'
                : 'bg-[var(--accent-red)] animate-pulse'
            }`}
          />
          <span className="text-[var(--text-muted)]">
            {connected ? 'WS Live' : 'WS Disconnesso'}
          </span>
        </div>
        {status && (
          <div className="flex items-center gap-1">
            <span
              className={`w-2 h-2 rounded-full ${
                status.stream_connected
                  ? 'bg-[var(--accent-green)]'
                  : 'bg-[var(--accent-yellow)] animate-pulse'
              }`}
            />
            <span className="text-[var(--text-muted)]">
              {status.stream_connected ? 'Stream X' : 'Polling'}
            </span>
          </div>
        )}
        {status?.is_running && (
          <span className="text-[var(--accent-yellow)] animate-pulse font-medium">
            ● Engine Running
          </span>
        )}
      </div>
    </header>
  );
}