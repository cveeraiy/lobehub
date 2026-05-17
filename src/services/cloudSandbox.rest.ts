import { restClient } from '@/libs/rest';

interface CallToolResult {
  content: string;
  error?: { code: string; message: string };
  success: boolean;
  type: string;
}

interface ExportAndUploadFileResult {
  filename: string;
  success: boolean;
  url: string;
}

class CloudSandboxService {
  async callTool(
    toolName: string,
    params: Record<string, any>,
    context: { topicId: string; userId?: string },
  ): Promise<CallToolResult> {
    return restClient.post<CallToolResult>('/cloud-sandbox/exec', {
      body: {
        params,
        toolName,
        topicId: context.topicId,
        userId: context.userId,
      },
    });
  }

  async exportAndUploadFile(
    path: string,
    filename: string,
    topicId: string,
  ): Promise<ExportAndUploadFileResult> {
    return restClient.post<ExportAndUploadFileResult>('/cloud-sandbox/export-and-upload', {
      body: {
        filename,
        path,
        topicId,
      },
    });
  }
}

export const cloudSandboxService = new CloudSandboxService();
