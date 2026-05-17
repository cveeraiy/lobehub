import { restClient } from '@/libs/rest';
import { uploadService } from '@/services/upload';
import { useUserStore } from '@/store/user';
import { type ImportPgDataStructure } from '@/types/export';
import { type ImporterEntryData, type OnImportCallbacks } from '@/types/importer';
import { ImportStage } from '@/types/importer';
import { type UserSettings } from '@/types/user/settings';
import { uuid } from '@/utils/uuid';

class ImportService {
  importSettings = async (settings: UserSettings): Promise<void> => {
    await useUserStore.getState().importAppSettings(settings);
  };

  importData = async (data: ImporterEntryData, callbacks?: OnImportCallbacks): Promise<void> => {
    const handleError = (e: unknown) => {
      callbacks?.onStageChange?.(ImportStage.Error);
      const error = e as any;

      callbacks?.onError?.({
        code: error?.code,
        httpStatus: error?.status,
        message: error?.message,
        path: error?.path,
      });
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
        const result = await restClient.post<{ results: any }>('/import', { body: { data } });
        const duration = Date.now() - time;

        callbacks?.onStageChange?.(ImportStage.Success);
        callbacks?.onSuccess?.(result.results, duration);
      } catch (e) {
        handleError(e);
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

    const handleError = (e: unknown) => {
      callbacks?.onStageChange?.(ImportStage.Error);
      const error = e as any;

      callbacks?.onError?.({
        code: error?.code,
        httpStatus: error?.status,
        message: error?.message,
        path: error?.path,
      });
    };

    const totalLength = Object.values(data.data)
      .map((d) => d.length)
      .reduce((a, b) => a + b, 0);

    if (totalLength < 500) {
      callbacks?.onStageChange?.(ImportStage.Importing);
      const time = Date.now();
      try {
        const result = await restClient.post<{ results: any }>('/import/pg', { body: data });
        const duration = Date.now() - time;

        callbacks?.onStageChange?.(ImportStage.Success);
        callbacks?.onSuccess?.(result.results, duration);
      } catch (e) {
        handleError(e);
      }

      return;
    }

    await this.uploadData(data, { callbacks, handleError });
  };

  private uploadData = async (
    data: object,
    { callbacks, handleError }: { callbacks?: OnImportCallbacks; handleError: (e: unknown) => any },
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
      const result = await restClient.post<{ results: any }>('/import/file', {
        body: { pathname },
      });
      const duration = Date.now() - time;
      callbacks?.onStageChange?.(ImportStage.Success);
      callbacks?.onSuccess?.(result.results, duration);
    } catch (e) {
      handleError(e);
    }
  };
}

export const importService = new ImportService();
