declare module 'next/server' {
  export const after: (callback: () => void | Promise<void>) => void;
}
