import { useTranslation } from 'react-i18next';

import SettingHeader from '@/routes/(main)/settings/features/SettingHeader';

import Conversation from './features/Conversation';
import Essential from './features/Essential';

const Page = () => {
  const { t } = useTranslation('setting');
  return (
    <>
      <SettingHeader title={t('tab.hotkey')} />
      <Essential />
      <Conversation />
    </>
  );
};

export default Page;
