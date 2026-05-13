import { Markdown } from '@lobehub/ui';
import { memo, type PropsWithChildren } from 'react';

const MarkdownRender = memo<PropsWithChildren>(({ children }) => {
  return <Markdown>{children as string}</Markdown>;
});

MarkdownRender.displayName = 'MarkdownRender';

export default MarkdownRender;
