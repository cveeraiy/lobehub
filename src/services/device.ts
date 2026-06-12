import { restClient } from '@/libs/rest';

interface DeviceGatewayStatus {
  capabilities: string[];
  configured: boolean;
  url?: string;
}

type DeviceProxyMethod = 'DELETE' | 'GET' | 'PATCH' | 'POST' | 'PUT';

class DeviceService {
  getStatus = async () => {
    return restClient.get<DeviceGatewayStatus>('/device/status');
  };

  proxy = async <T = unknown>(
    path: string,
    options: {
      body?: unknown;
      method?: DeviceProxyMethod;
      params?: Record<string, boolean | number | string | undefined>;
    } = {},
  ) => {
    const proxyPath = `/device/proxy/${path.replace(/^\/+/, '')}`;
    const method = options.method ?? 'GET';

    switch (method) {
      case 'DELETE': {
        return restClient.delete<T>(proxyPath, { body: options.body, params: options.params });
      }
      case 'PATCH': {
        return restClient.patch<T>(proxyPath, { body: options.body, params: options.params });
      }
      case 'POST': {
        return restClient.post<T>(proxyPath, { body: options.body, params: options.params });
      }
      case 'PUT': {
        return restClient.put<T>(proxyPath, { body: options.body, params: options.params });
      }
      default: {
        return restClient.get<T>(proxyPath, { params: options.params });
      }
    }
  };
}

export const deviceService = new DeviceService();
