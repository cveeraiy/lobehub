import { restClient } from '@/libs/rest';
import { globalHelpers } from '@/store/global/helpers';
import { type PluginQueryParams } from '@/types/discover';
import { getToolManifest } from '@/utils/toolManifest';

class ToolService {
  getOldPluginList = async (params: PluginQueryParams): Promise<any> => {
    const locale = globalHelpers.getCurrentLanguage();

    return restClient.get('/discover/plugin/list', {
      params: {
        ...params,
        locale,
        page: params.page ? Number(params.page) : 1,
        pageSize: params.pageSize ? Number(params.pageSize) : 20,
      } as any,
    });
  };

  getToolManifest = getToolManifest;
}

export const toolService = new ToolService();
