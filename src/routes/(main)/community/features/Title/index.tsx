import { Flexbox } from '@lobehub/ui';
import { Typography } from 'antd';
import { memo, type PropsWithChildren, type ReactNode } from 'react';

const { Title: AntTitle } = Typography;

export interface TitleProps extends PropsWithChildren {
  icon?: ReactNode;
  id?: string;
  level?: 1 | 2 | 3 | 4 | 5;
  more?: ReactNode;
  moreLink?: string;
  tag?: ReactNode;
}

const Title = memo<TitleProps>(({ children, icon, id, level = 3, more, moreLink, tag }) => {
  return (
    <Flexbox horizontal align={'center'} justify={'space-between'}>
      <Flexbox horizontal align={'center'} gap={8}>
        {icon}
        <AntTitle id={id} level={level} style={{ margin: 0 }}>
          {children}
        </AntTitle>
        {tag}
      </Flexbox>
      {more && moreLink && <a href={moreLink}>{more}</a>}
    </Flexbox>
  );
});

Title.displayName = 'Title';

export default Title;
