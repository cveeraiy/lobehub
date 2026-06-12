import { restClient } from '@/libs/rest';
import { uploadService } from '@/services/upload';
import { useUserStore } from '@/store/user';
import { type ImportPgDataStructure } from '@/types/export';
import {
  type ErrorShape,
  type ImporterEntryData,
  type ImportResults,
  type OnImportCallbacks,
} from '@/types/importer';
import { ImportStage } from '@/types/importer';
import { type UserSettings } from '@/types/user/settings';
import { uuid } from '@/utils/uuid';

interface ImportResponse {
  results: ImportResults;
}

interface RestLikeError {
  code?: string;
  data?: {
    code?: string;
    httpStatus?: number;
    path?: string;
  };
  message?: string;
  path?: string;
  status?: number;
}

const toImportError = (error: unknown): ErrorShape => {
  const restError = error as RestLikeError;

  return {
    code: restError.code ?? restError.data?.code ?? 'INTERNAL_SERVER_ERROR',
    httpStatus: restError.status ?? restError.data?.httpStatus ?? 500,
    message: restError.message ?? 'Import failed',
    path: restError.path ?? restError.data?.path,
  };
};

class ImportService {
  importSettings = async (settings: UserSettings): Promise<void> => {
    await useUserStore.getState().importAppSettings(settings);
  };

  importData = async (data: ImporterEntryData, callbacks?: OnImportCallbacks): Promise<void> => {
    const handleError = (error: unknown) => {
      callbacks?.onStageChange?.(ImportStage.Error);
      callbacks?.onError?.(toImportError(error));
    };

    const totalLength =
      (data.messages?.length || 0) +
      (data.sessionGroups?.length || 0) +
      (data.sessions?.length || 0) +
      (data.topics?.length || 0);

    if (totalLength < 500) {
      callbacks?.onStageChange?.(ImportStage.Importing);
      const time = Date.now();
      try {
        const result = await restClient.post<ImportResponse>('/import', { body: { data } });
        const duration = Date.now() - time;

        callbacks?.onStageChange?.(ImportStage.Success);
        callbacks?.onSuccess?.(result.results, duration);
      } catch (error) {
        handleError(error);
      }

      return;
    }

    await this.uploadData(data, { callbacks, handleError });
  };

  importPgData = async (
    data: ImportPgDataStructure,
    options?: {
      callbacks?: OnImportCallbacks;
      overwriteExisting?: boolean;
    },
  ): Promise<void> => {
    const { callbacks } = options || {};

    const handleError = (error: unknown) => {
      callbacks?.onStageChange?.(ImportStage.Error);
      callbacks?.onError?.(toImportError(error));
    };

    const totalLength = Object.values(data.data)
      .map((d) => d.length)
      .reduce((a, b) => a + b, 0);

    if (totalLength < 500) {
      callbacks?.onStageChange?.(ImportStage.Importing);
      const time = Date.now();
      try {
        const result = await restClient.post<ImportResponse>('/import/pg', { body: data });
        const duration = Date.now() - time;

        callbacks?.onStageChange?.(ImportStage.Success);
        callbacks?.onSuccess?.(result.results, duration);
      } catch (error) {
        handleError(error);
      }

      return;
    }

    await this.uploadData(data, { callbacks, handleError });
  };

  private uploadData = async (
    data: object,
    {
      callbacks,
      handleError,
    }: { callbacks?: OnImportCallbacks; handleError: (error: unknown) => void },
  ) => {
    const filename = `${uuid()}.json`;

    let pathname;
    try {
      callbacks?.onStageChange?.(ImportStage.Uploading);
      const result = await uploadService.uploadDataToS3(data, {
        filename,
        onProgress: (status, state) => {
          callbacks?.onFileUploading?.(state);
        },
        pathname: `import_config/${filename}`,
      });
      pathname = result.data.path;
    } catch {
      throw new Error('Upload Error');
    }

    callbacks?.onStageChange?.(ImportStage.Importing);
    const time = Date.now();
    try {
      const result = await restClient.post<ImportResponse>('/import/file', {
        body: { pathname },
      });
      const duration = Date.now() - time;
      callbacks?.onStageChange?.(ImportStage.Success);
      callbacks?.onSuccess?.(result.results, duration);
    } catch (error) {
      handleError(error);
    }
  };
}

export const importService = new ImportService();
