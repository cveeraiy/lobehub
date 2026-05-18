import { lambdaClient } from '@/libs/trpc/client';
import { type ExportDatabaseData } from '@/types/export';

interface ExportPdfParams {
  content: string;
  sessionId: string;
  title: string;
  topicId?: string;
}

class ExportService {
  exportData = async (): Promise<ExportDatabaseData> => {
    return await lambdaClient.exporter.exportData.mutate();
  };

  exportPdf = async (params: ExportPdfParams): Promise<{ filename: string; pdf: string }> => {
    return lambdaClient.exporter.exportPdf.mutate(params);
  };
}

export const exportService = new ExportService();
