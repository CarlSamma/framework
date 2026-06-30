import { useState } from 'react';
import { api } from '../../hooks/useApi';
import { FollowUpCard } from './FollowUpCard';
import type { FollowUpState } from '../../types/tap';

export function ProbeComposer({ isRunning }: { isRunning: boolean }) {
  const [followUpState, setFollowUpState] = useState<FollowUpState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.generateOptions();
      const state = await api.followup();
      setFollowUpState(state);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore sconosciuto');
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = async (choice: 'A' | 'B') => {
    await api.selectOption(choice);
    setFollowUpState(prev =>
      prev
        ? {
            ...prev,
            selected_probe:
              choice === 'A' ? prev.followup!.option_a : prev.followup!.option_b,
          }
        : null
    );
  };

  const handlePost = async () => {
    setLoading(true);
    try {
      await api.postSelected();
      setFollowUpState(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Post fallito');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    await api.resetEngine();
    setFollowUpState(null);
    setError(null);
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button
          onClick={handleGenerate}
          disabled={isRunning || loading}
          className="flex-1 py-2 px-4 rounded bg-[var(--accent-blue)] text-white text-sm font-medium disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          {loading ? 'Generazione...' : '⚡ Genera Probe A/B'}
        </button>
        <button
          onClick={handleReset}
          className="py-2 px-3 rounded bg-[var(--bg-border)] text-[var(--text-muted)] text-sm hover:bg-red-900 hover:text-white transition-colors"
          title="Force Reset Engine"
        >
          ↺
        </button>
      </div>

      {error && (
        <p className="text-xs text-[var(--accent-red)] bg-red-950 rounded p-2">{error}</p>
      )}

      {isRunning && (
        <div className="flex items-center gap-2 text-sm text-[var(--accent-yellow)] bg-yellow-950 rounded p-2">
          <span className="animate-pulse">●</span> Ciclo in esecuzione...
        </div>
      )}

      {followUpState?.followup && !isRunning && (
        <FollowUpCard
          followup={followUpState.followup}
          selected={followUpState.selected_probe}
          onSelect={handleSelect}
          onPost={handlePost}
          loading={loading}
        />
      )}
    </div>
  );
}