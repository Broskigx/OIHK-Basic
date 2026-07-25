import { useCallback, useState } from "react";
import { targetIntake, ingestText, ingestUrl, uploadTargetPhotos } from "../api";
import type { IntakeForm, SourceForm } from "../types";

const defaultIntake: IntakeForm = {
  first_name: "",
  last_name: "",
  aliases: "",
  notes: "",
  legal_basis: "",
  scope_statement: "",
  consent_basis: "",
  auto_search: true,
  photos: [] as File[],
};

const defaultSourceForm: SourceForm = {
  mode: "text",
  title: "Analyst evidence",
  body: "",
  url: "",
  citation: "Analyst note",
  license: "case-note",
  reliability: 0.7,
};

export interface IntakeFormState {
  intake: IntakeForm;
  sourceForm: SourceForm;
  photoUploading: boolean;
}

export interface IntakeFormActions {
  patchIntake: (patch: Partial<IntakeForm>) => void;
  patchSourceForm: (patch: Partial<SourceForm>) => void;
  submitIntake: (
    event: React.FormEvent,
    onSuccess: (caseId: string, refresh: () => Promise<void>) => Promise<void>,
    onError: (msg: string) => void,
  ) => Promise<void>;
  submitEvidence: (
    event: React.FormEvent,
    activeCaseId: string,
    refresh: () => Promise<void>,
    onError: (msg: string) => void,
  ) => Promise<void>;
  addPersonPhotos: (
    event: React.ChangeEvent<HTMLInputElement>,
    activeTargetId: string,
    activeCaseId: string | undefined,
    refresh: () => Promise<void>,
    onError: (msg: string) => void,
  ) => Promise<void>;
  presetSource: (mode: string, title: string) => void;
  resetIntake: () => void;
}

export function useIntakeForm(): IntakeFormState & IntakeFormActions {
  const [intake, setIntake] = useState<IntakeForm>(defaultIntake);
  const [sourceForm, setSourceForm] = useState<SourceForm>(defaultSourceForm);
  const [photoUploading, setPhotoUploading] = useState(false);

  const patchIntake = useCallback((patch: Partial<IntakeForm>) => {
    setIntake((prev) => ({ ...prev, ...patch }));
  }, []);

  const patchSourceForm = useCallback((patch: Partial<SourceForm>) => {
    setSourceForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const presetSource = useCallback((mode: string, title: string) => {
    setSourceForm((prev) => ({ ...prev, mode, title }));
  }, []);

  const submitIntake = useCallback(
    async (
      event: React.FormEvent,
      onSuccess: (caseId: string, refresh: () => Promise<void>) => Promise<void>,
      onError: (msg: string) => void,
    ) => {
      event.preventDefault();
      try {
        const result = await targetIntake(intake);
        await onSuccess(result.case.id, async () => {});
      } catch (err) {
        onError(err instanceof Error ? err.message : "No se pudo iniciar la busqueda");
      }
    },
    [intake],
  );

  const submitEvidence = useCallback(
    async (
      event: React.FormEvent,
      activeCaseId: string,
      refresh: () => Promise<void>,
      onError: (msg: string) => void,
    ) => {
      event.preventDefault();
      if (!activeCaseId) return;
      try {
        if (sourceForm.mode === "url") {
          await ingestUrl({
            case_id: activeCaseId,
            url: sourceForm.url,
            title: sourceForm.title || undefined,
            license: sourceForm.license,
            reliability: sourceForm.reliability,
          });
        } else {
          await ingestText({
            case_id: activeCaseId,
            title: sourceForm.title,
            body: sourceForm.body,
            citation: sourceForm.citation,
            license: sourceForm.license,
            reliability: sourceForm.reliability,
          });
        }
        await refresh();
      } catch (err) {
        onError(err instanceof Error ? err.message : "No se pudo guardar evidencia");
      }
    },
    [sourceForm],
  );

  const addPersonPhotos = useCallback(
    async (
      event: React.ChangeEvent<HTMLInputElement>,
      activeTargetId: string,
      activeCaseId: string | undefined,
      refresh: () => Promise<void>,
      onError: (msg: string) => void,
    ) => {
      const files = Array.from(event.target.files ?? []);
      if (!activeTargetId || files.length === 0) return;
      setPhotoUploading(true);
      try {
        await uploadTargetPhotos(activeTargetId, files);
        if (activeCaseId) await refresh();
      } catch (err) {
        onError(err instanceof Error ? err.message : "No se pudieron adjuntar las fotos");
      } finally {
        setPhotoUploading(false);
        event.target.value = "";
      }
    },
    [],
  );

  const resetIntake = useCallback(() => {
    setIntake(defaultIntake);
    setSourceForm(defaultSourceForm);
  }, []);

  return {
    intake,
    sourceForm,
    photoUploading,
    patchIntake,
    patchSourceForm,
    submitIntake,
    submitEvidence,
    addPersonPhotos,
    presetSource,
    resetIntake,
  };
}
