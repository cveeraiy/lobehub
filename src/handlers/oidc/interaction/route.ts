import { authEnv } from '@/envs/auth';
import { defaultClients } from '@/libs/oidc-provider/config';
import { OIDCService } from '@/server/services/oidc';

export async function GET(request: Request) {
  if (!authEnv.ENABLE_OIDC) {
    return Response.json({ error: 'OIDC is not enabled' }, { status: 404 });
  }

  const url = new URL(request.url);
  const uid = url.searchParams.get('uid');

  if (!uid) {
    return Response.json({ error: 'uid parameter is required' }, { status: 400 });
  }

  try {
    const oidcService = await OIDCService.initialize();
    const details = await oidcService.getInteractionDetails(uid, request);

    if (details.prompt.name !== 'consent' && details.prompt.name !== 'login') {
      return Response.json({
        error: 'unsupported_interaction',
        promptName: details.prompt.name,
      });
    }

    const clientId = (details.params.client_id as string) || 'unknown';
    const scopes = (details.params.scope as string)?.split(' ') || [];

    const clientDetail = await oidcService.getClientMetadata(clientId);

    return Response.json({
      clientId,
      clientMetadata: {
        clientName: clientDetail?.client_name,
        isFirstParty: defaultClients.map((c) => c.client_id).includes(clientId),
        logo: clientDetail?.logo_uri,
      },
      promptName: details.prompt.name,
      redirectUri: details.params.redirect_uri as string,
      scopes,
    });
  } catch (error) {
    console.error('Error fetching OIDC interaction:', error);
    const errorMessage = error instanceof Error ? error.message : undefined;

    if (errorMessage?.includes('interaction session not found')) {
      return Response.json({ error: 'session_invalid', message: errorMessage }, { status: 400 });
    }

    return Response.json({ error: 'server_error', message: errorMessage }, { status: 500 });
  }
}
