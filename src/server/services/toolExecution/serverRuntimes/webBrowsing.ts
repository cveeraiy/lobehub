import { WebBrowsingManifest } from '@lobechat/builtin-tools';
import { WebBrowsingExecutionRuntime } from '@lobechat/builtin-tools/webBrowsingExecutionRuntime';

import { DocumentModel } from '@/database/models/document';
import { AgentDocumentsService } from '@/server/services/agentDocuments';
import { PythonSearchProxyService } from '@/server/services/pythonSearchProxy';

import { type ServerRuntimeRegistration } from './types';

export const webBrowsingRuntime: ServerRuntimeRegistration = {
  factory: (context) => {
    const { userId, serverDB, agentId } = context;

    if (!userId) {
      throw new Error('userId is required for Web Browsing execution');
    }

    const canSaveDocuments = userId && serverDB && agentId;

    return new WebBrowsingExecutionRuntime({
      documentService: canSaveDocuments
        ? {
            associateDocument: async (documentId) => {
              const service = new AgentDocumentsService(serverDB, userId);
              await service.associateDocument(agentId, documentId);
            },
            createDocument: async ({ content, description, title, url }) => {
              const model = new DocumentModel(serverDB, userId);
              return model.create({
                content,
                description,
                fileType: 'article',
                filename: title,
                source: url,
                sourceType: 'web',
                title,
                totalCharCount: content.length,
                totalLineCount: content.split('\n').length,
              });
            },
          }
        : undefined,
      searchService: new PythonSearchProxyService(userId),
    });
  },
  identifier: WebBrowsingManifest.identifier,
};
