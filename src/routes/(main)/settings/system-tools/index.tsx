import { useTranslation } from 'react-i18next';

import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';

const Page = () => {
  const { t } = useTranslation('setting');

  return <SettingHeader title={t('tab.systemTools')} />;
};

export default Page;
