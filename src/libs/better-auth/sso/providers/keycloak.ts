import { authEnv } from '@/envs/auth';

import { buildOidcConfig } from '../helpers';
import { type GenericProviderDefinition } from '../types';

/**
 * Extract LobeHub role from Keycloak realm roles.
 * Keycloak includes `realm_access.roles` in the OIDC profile when
 * the client has a realm-role mapper configured.
 */
const ROLE_PRIORITY = ['super_admin', 'admin', 'user', 'viewer'] as const;

const mapKeycloakRole = (profile: Record<string, any>): string => {
  const roles: string[] = profile?.realm_access?.roles ?? profile?.['realm_access.roles'] ?? [];
  return ROLE_PRIORITY.find((r) => roles.includes(r)) ?? 'user';
};

const provider: GenericProviderDefinition<{
  AUTH_KEYCLOAK_ID: string;
  AUTH_KEYCLOAK_ISSUER: string;
  AUTH_KEYCLOAK_SECRET: string;
}> = {
  build: (env) =>
    buildOidcConfig({
      clientId: env.AUTH_KEYCLOAK_ID,
      clientSecret: env.AUTH_KEYCLOAK_SECRET,
      issuer: env.AUTH_KEYCLOAK_ISSUER,
      overrides: {
        mapProfileToUser: (profile) => ({
          name: profile.name ?? profile.preferred_username ?? profile.email ?? profile.sub,
          role: mapKeycloakRole(profile),
        }),
      },
      providerId: 'keycloak',
      scopes: ['openid', 'email', 'profile', 'roles'],
    }),
  checkEnvs: () => {
    return !!(
      authEnv.AUTH_KEYCLOAK_ID &&
      authEnv.AUTH_KEYCLOAK_SECRET &&
      authEnv.AUTH_KEYCLOAK_ISSUER
    )
      ? {
          AUTH_KEYCLOAK_ID: authEnv.AUTH_KEYCLOAK_ID,
          AUTH_KEYCLOAK_ISSUER: authEnv.AUTH_KEYCLOAK_ISSUER,
          AUTH_KEYCLOAK_SECRET: authEnv.AUTH_KEYCLOAK_SECRET,
        }
      : false;
  },
  id: 'keycloak',
  type: 'generic',
};

export default provider;
