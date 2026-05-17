import { restClient } from '@/libs/rest';
import { type ExportDatabaseData } from '@/types/export';

class ExportService {
  exportData = async (): Promise<ExportDatabaseData> => {
    return restClient.get<ExportDatabaseData>('/export/all');
  };
}

export const exportService = new ExportService();
