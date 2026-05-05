import { getServerDBConfig } from '@/config/db';
import { GatewayService } from '@/server/services/gateway';

export const POST = async (req: Request): Promise<Response> => {
  const { KEY_VAULTS_SECRET } = getServerDBConfig();

  const authHeader = req.headers.get('authorization');
  if (authHeader !== `Bearer ${KEY_VAULTS_SECRET}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const service = new GatewayService();

  try {
    if (body.restart) {
      console.info('[GatewayService] Restarting...');
      await service.stop();
    }

    await service.ensureRunning();
    console.info('[GatewayService] Started successfully');

    return Response.json({ status: body.restart ? 'restarted' : 'started' });
  } catch (error) {
    console.error('[GatewayService] Failed to start:', error);
    return Response.json({ error: 'Failed to start gateway' }, { status: 500 });
  }
};
