import { AgentDocumentsExecutionRuntime } from '@lobechat/builtin-tools/agentDocumentsExecutionRuntime';
import { describe, expect, it, vi } from 'vitest';

import { callPythonBackend } from '@/server/utils/pythonBackend';

import { agentDocumentsRuntime } from '../agentDocuments';

vi.mock('@/server/utils/pythonBackend');

describe('agentDocumentsRuntime', () => {
  it('should have correct identifier', () => {
    expect(agentDocumentsRuntime.identifier).toBe('lobe-agent-documents');
  });

  it('should call Python tool execution with agent and scope context', async () => {
    vi.mocked(callPythonBackend).mockResolvedValue({
      result: JSON.stringify({ content: 'ok', success: true }),
    });
    const runtime = agentDocumentsRuntime.factory({
      agentId: 'agent-1',
      documentId: 'documents-row-id',
      scope: 'page',
      taskId: 'task-1',
      toolManifestMap: {},
      topicId: 'topic-1',
      userId: 'user-1',
    });

    const result = await runtime.replaceDocumentContent({
      content: 'updated',
      id: 'agent-doc-assoc-id',
    });

    expect(result).toEqual({ content: 'ok', success: true });
    expect(callPythonBackend).toHaveBeenCalledWith('/api/tools/run', 'user-1', {
      body: {
        arguments: {
          agentId: 'agent-1',
          content: 'updated',
          currentDocumentId: 'documents-row-id',
          id: 'agent-doc-assoc-id',
          scope: 'page',
          taskId: 'task-1',
          topicId: 'topic-1',
        },
        tool_name: 'lobe-agent-documents__replaceDocumentContent',
      },
    });
  });

  it('should throw at execution time if userId is missing', async () => {
    const runtime = agentDocumentsRuntime.factory({ toolManifestMap: {} });

    await expect(runtime.readDocument({ id: 'agent-doc-assoc-id' })).rejects.toThrow(
      'userId is required for Agent Documents execution',
    );
  });
});

describe('AgentDocumentsExecutionRuntime.createDocument', () => {
  const makeStub = () => ({
    copyDocument: vi.fn(),
    createDocument: vi.fn(),
    createTopicDocument: vi.fn(),
    listDocuments: vi.fn(),
    listTopicDocuments: vi.fn(),
    modifyNodes: vi.fn(),
    readDocument: vi.fn(),
    removeDocument: vi.fn(),
    renameDocument: vi.fn(),
    replaceDocumentContent: vi.fn(),
    updateLoadRule: vi.fn(),
  });

  it('returns documents.id (not agentDocuments.id) for state.documentId', async () => {
    const stub = makeStub();
    stub.createDocument.mockResolvedValue({
      documentId: 'documents-row-id',
      filename: 'daily-brief',
      id: 'agent-doc-assoc-id',
      title: 'Daily Brief',
    });

    const runtime = new AgentDocumentsExecutionRuntime(stub);
    const result = await runtime.createDocument(
      { content: 'body', title: 'Daily Brief' },
      { agentId: 'agent-1' },
    );

    expect(result.success).toBe(true);
    expect(result.state).toEqual({ documentId: 'documents-row-id' });
  });

  it('refuses to run without agentId', async () => {
    const stub = makeStub();
    const runtime = new AgentDocumentsExecutionRuntime(stub);

    const result = await runtime.createDocument({ content: 'body', title: 'T' }, {});

    expect(result.success).toBe(false);
    expect(stub.createDocument).not.toHaveBeenCalled();
  });

  it('creates a document in the current topic when target is currentTopic', async () => {
    const stub = makeStub();
    stub.createTopicDocument.mockResolvedValue({
      documentId: 'documents-row-id',
      filename: 'topic-note',
      id: 'agent-doc-assoc-id',
      title: 'Topic Note',
    });

    const runtime = new AgentDocumentsExecutionRuntime(stub);
    const result = await runtime.createDocument(
      { content: 'body', target: 'currentTopic', title: 'Topic Note' },
      { agentId: 'agent-1', topicId: 'topic-1' },
    );

    expect(result.success).toBe(true);
    expect(result.state).toEqual({ documentId: 'documents-row-id' });
    expect(stub.createTopicDocument).toHaveBeenCalledWith({
      agentId: 'agent-1',
      content: 'body',
      target: 'currentTopic',
      title: 'Topic Note',
      topicId: 'topic-1',
    });
    expect(stub.createDocument).not.toHaveBeenCalled();
  });

  it('refuses current topic creation without topicId', async () => {
    const stub = makeStub();
    const runtime = new AgentDocumentsExecutionRuntime(stub);

    const result = await runtime.createDocument(
      { content: 'body', target: 'currentTopic', title: 'Topic Note' },
      { agentId: 'agent-1' },
    );

    expect(result).toMatchObject({
      content: 'Cannot create current topic document without topicId context.',
      success: false,
    });
    expect(stub.createTopicDocument).not.toHaveBeenCalled();
  });

  it('blocks replaceDocumentContent for the current page document', async () => {
    const stub = makeStub();
    stub.readDocument.mockResolvedValue({
      content: 'body',
      documentId: 'documents-row-id',
      id: 'agent-doc-assoc-id',
      title: 'Daily Brief',
    });

    const runtime = new AgentDocumentsExecutionRuntime(stub);
    const result = await runtime.replaceDocumentContent(
      { content: 'updated', id: 'agent-doc-assoc-id' },
      {
        agentId: 'agent-1',
        currentDocumentId: 'documents-row-id',
        scope: 'page',
      },
    );

    expect(result.success).toBe(false);
    expect(result.error).toMatchObject({
      code: 'CURRENT_PAGE_DOCUMENT_WRITE_FORBIDDEN',
      kind: 'replan',
    });
    expect(stub.replaceDocumentContent).not.toHaveBeenCalled();
  });

  it('still allows replacing a different agent document in page scope', async () => {
    const stub = makeStub();
    stub.readDocument.mockResolvedValue({
      content: 'body',
      documentId: 'documents-row-id-2',
      id: 'agent-doc-assoc-id-2',
      title: 'Other Doc',
    });
    stub.replaceDocumentContent.mockResolvedValue({
      content: 'updated',
      documentId: 'documents-row-id-2',
      id: 'agent-doc-assoc-id-2',
      title: 'Other Doc',
    });

    const runtime = new AgentDocumentsExecutionRuntime(stub);
    const result = await runtime.replaceDocumentContent(
      { content: 'updated', id: 'agent-doc-assoc-id-2' },
      {
        agentId: 'agent-1',
        currentDocumentId: 'documents-row-id',
        scope: 'page',
      },
    );

    expect(result.success).toBe(true);
    expect(stub.replaceDocumentContent).toHaveBeenCalledWith({
      agentId: 'agent-1',
      content: 'updated',
      id: 'agent-doc-assoc-id-2',
    });
  });
});

describe('AgentDocumentsExecutionRuntime.listDocuments', () => {
  const makeStub = () => ({
    copyDocument: vi.fn(),
    createDocument: vi.fn(),
    createTopicDocument: vi.fn(),
    listDocuments: vi.fn(),
    listTopicDocuments: vi.fn(),
    modifyNodes: vi.fn(),
    readDocument: vi.fn(),
    removeDocument: vi.fn(),
    renameDocument: vi.fn(),
    replaceDocumentContent: vi.fn(),
    updateLoadRule: vi.fn(),
  });

  it('lists current topic documents while preserving agent document ids', async () => {
    const stub = makeStub();
    stub.listTopicDocuments.mockResolvedValue([
      {
        documentId: 'documents-row-id',
        filename: 'topic-note',
        id: 'agent-doc-assoc-id',
        title: 'Topic Note',
      },
    ]);

    const runtime = new AgentDocumentsExecutionRuntime(stub);
    const result = await runtime.listDocuments(
      { target: 'currentTopic' },
      { agentId: 'agent-1', topicId: 'topic-1' },
    );

    const documents = [
      {
        documentId: 'documents-row-id',
        filename: 'topic-note',
        id: 'agent-doc-assoc-id',
        title: 'Topic Note',
      },
    ];
    expect(result).toEqual({
      content: JSON.stringify(documents),
      state: { documents },
      success: true,
    });
    expect(stub.listTopicDocuments).toHaveBeenCalledWith({
      agentId: 'agent-1',
      target: 'currentTopic',
      topicId: 'topic-1',
    });
    expect(stub.listDocuments).not.toHaveBeenCalled();
  });
});
