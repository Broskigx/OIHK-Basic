import { useCallback, useState } from "react";
import { autoInvestigateStream } from "../api";
import { initialProgress, reduceProgressEvent } from "../investigationProgress";
import type { InvestigationProgress } from "../investigationProgress";
import type { CaseSummary } from "../types";

export interface InvestigationState {
  autoSummary: CaseSummary | null;
  progress: InvestigationProgress | null;
}

export interface InvestigationActions {
  submitAuto: (
    intake: { first_name: string; last_name: string; aliases: string; notes: string },
    onSuccess: (caseId: string, refresh: () => Promise<void>) => Promise<void>,
    onError: (msg: string) => void,
  ) => Promise<void>;
}

export function useInvestigation(): InvestigationState & InvestigationActions {
  const [autoSummary, setAutoSummary] = useState<CaseSummary | null>(null);
  const [progress, setProgress] = useState<InvestigationProgress | null>(null);

  const submitAuto = useCallback(
    async (
      intake: { first_name: string; last_name: string; aliases: string; notes: string },
      onSuccess: (caseId: string, refresh: () => Promise<void>) => Promise<void>,
      onError: (msg: string) => void,
    ) => {
      setAutoSummary(null);
      setProgress({ ...initialProgress, active: true });
      let finalCaseId = "";
      try {
        await autoInvestigateStream(intake, (streamEvent) => {
          setProgress((prev) => {
            const base = prev ?? initialProgress;
            const next = reduceProgressEvent(base, streamEvent);
            if (streamEvent.phase === "done") {
              finalCaseId = streamEvent.case_id ?? "";
              if (streamEvent.summary) setAutoSummary(streamEvent.summary);
            }
            if (streamEvent.phase === "error") {
              onError(streamEvent.message ?? "La investigación falló");
            }
            return next;
          });
        });
        if (finalCaseId) {
          await onSuccess(finalCaseId, async () => {});
        }
      } catch (err) {
        onError(err instanceof Error ? err.message : "No se pudo completar la investigación automática");
        setProgress((prev) => (prev ? { ...prev, active: false, failed: true } : prev));
      } finally {
        setProgress((prev) => (prev ? { ...prev, active: false } : prev));
      }
    },
    [],
  );

  return { autoSummary, progress, submitAuto };
}
