export const WebOnboardingIdentifier = 'lobe-web-onboarding';

export const WebOnboardingApiName = {
  finishOnboarding: 'finishOnboarding',
  readDocument: 'readDocument',
  saveUserQuestion: 'saveUserQuestion',
  updateDocument: 'updateDocument',
  writeDocument: 'writeDocument',
} as const;

export type WebOnboardingDocumentType = 'persona' | 'soul';

export type MarkdownPatchMode = 'replace' | 'delete' | 'deleteLines' | 'insertAt' | 'replaceLines';

export interface MarkdownPatchReplaceHunk {
  mode?: 'replace';
  replace: string;
  replaceAll?: boolean;
  search: string;
}

export interface MarkdownPatchDeleteHunk {
  mode: 'delete';
  replaceAll?: boolean;
  search: string;
}

export interface MarkdownPatchDeleteLinesHunk {
  endLine: number;
  mode: 'deleteLines';
  startLine: number;
}

export interface MarkdownPatchInsertAtHunk {
  content: string;
  line: number;
  mode: 'insertAt';
}

export interface MarkdownPatchReplaceLinesHunk {
  content: string;
  endLine: number;
  mode: 'replaceLines';
  startLine: number;
}

export type MarkdownPatchHunk =
  | MarkdownPatchReplaceHunk
  | MarkdownPatchDeleteHunk
  | MarkdownPatchDeleteLinesHunk
  | MarkdownPatchInsertAtHunk
  | MarkdownPatchReplaceLinesHunk;

export interface UpdateDocumentArgs {
  hunks: MarkdownPatchHunk[];
  type: WebOnboardingDocumentType;
}
