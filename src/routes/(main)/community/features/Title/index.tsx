import { Flexbox } from '@lobehub/ui';
import { Typography } from 'antd';
import { memo, type PropsWithChildren, type ReactNode } from 'react';

const { Title: AntTitle } = Typography;

export interface TitleProps extends PropsWithChildren {
  level?: 1 | 2 | 3 | 4 | 5;
  more?: ReactNode;
  moreLink?: string;
}

const Title = memo<TitleProps>(({ children, level = 3, more, moreLink }) => {
  return (
    <Flexbox horizontal align={'center'} justify={'space-between'}>
      <AntTitle level={level} style={{ margin: 0 }}>
        {children}
      </AntTitle>
      {more && moreLink && <a href={moreLink}>{more}</a>}
    </Flexbox>
  );
});

Title.displayName = 'Title';

export default Title;
