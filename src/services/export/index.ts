import { restClient } from '@/libs/rest';
import { type ExportDatabaseData } from '@/types/export';

interface ExportPdfParams {
  content: string;
  sessionId: string;
  title: string;
  topicId?: string;
}

class ExportService {
  exportData = async (): Promise<ExportDatabaseData> => {
    return restClient.get<ExportDatabaseData>('/export/all');
  };

  exportPdf = async (params: ExportPdfParams): Promise<{ filename: string; pdf: string }> => {
    return restClient.post('/export/pdf', {
      body: {
        content: params.content,
        session_id: params.sessionId,
        title: params.title,
        topic_id: params.topicId,
      },
    });
  };
}

export const exportService = new ExportService();
