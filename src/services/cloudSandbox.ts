import { restClient } from '@/libs/rest';

interface CallToolResult {
  error?: { message: string; name?: string };
  result: {
    exitCode?: number;
    output?: string;
    stderr?: string;
    stdout?: string;
  } | null;
  sessionExpiredAndRecreated?: boolean;
  success: boolean;
}

interface ExportAndUploadFileResult {
  error?: { message: string };
  fileId?: string;
  filename: string;
  mimeType?: string;
  size?: number;
  success: boolean;
  url?: string;
}

class CloudSandboxService {
  /**
   * Call a cloud sandbox tool
   * @param toolName - The name of the tool to call (e.g., 'runCommand', 'writeLocalFile')
   * @param params - The parameters for the tool
   * @param context - Session context containing topicId and optional userId for isolation
   */
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

  /**
   * Export a file from sandbox and upload to S3, then create a persistent file record
   * This is a single call that combines: getUploadUrl + callTool(exportFile) + createFileRecord
   * Returns a permanent /f/:id URL instead of a temporary pre-signed URL
   * @param path - The file path in the sandbox
   * @param filename - The name of the file to export
   * @param topicId - The topic ID for organizing files
   */
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
