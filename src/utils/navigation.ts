/**
 * Check if user is performing a modifier click (Cmd+Click on Mac, Ctrl+Click on other OS)
 * to open link in new tab.
 */
export const isModifierClick = (e: { ctrlKey: boolean; metaKey: boolean }): boolean => {
  return e.metaKey || e.ctrlKey;
};
