/**
 * Default maximum length for tool execution result content (in characters).
 * This prevents context overflow when sending results back to LLM.
 */
export const DEFAULT_TOOL_RESULT_MAX_LENGTH = 25_000;

export function truncateToolResult(content: string, maxLength?: number): string {
  const limit = maxLength ?? DEFAULT_TOOL_RESULT_MAX_LENGTH;

  if (!content || content.length <= limit) {
    return content;
  }

  const truncated = content.slice(0, limit);
  const remainingChars = content.length - limit;
  const notice = `\n\n[Content truncated: ${remainingChars.toLocaleString()} characters omitted to prevent context overflow. Original length: ${content.length.toLocaleString()} characters]`;

  return truncated + notice;
}

export function truncateToolResultWithState<T extends { content: string; state?: any }>(
  result: T,
  maxLength?: number,
): T {
  return {
    ...result,
    content: truncateToolResult(result.content, maxLength),
  };
}
