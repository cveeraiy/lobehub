/**
 * Lobe Notebook Executor
 *
 * Creates and exports the NotebookExecutor instance for registration.
 * Injects notebookService as dependency.
 */
import { NotebookExecutor } from '@lobechat/builtin-tools/notebookExecutor';

import { notebookService } from '@/services/notebook';

// Create executor instance with client-side service
export const notebookExecutor = new NotebookExecutor(notebookService);
