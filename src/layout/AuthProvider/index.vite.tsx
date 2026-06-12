import { type PropsWithChildren } from 'react';

import BetterAuth from './BetterAuth';

const AuthProvider = ({ children }: PropsWithChildren) => {
  // In SPA/Vite mode, always use BetterAuth.
  // If auth is not configured on the server, useSession() will return no session
  // and the user will be treated as not signed in — same effect as NoAuth.
  return <BetterAuth>{children}</BetterAuth>;
};

export default AuthProvider;
