import { Flexbox } from '@lobehub/ui';
import { useInfiniteQuery } from '@tanstack/react-query';
import { memo } from 'react';
import { Virtuoso } from 'react-virtuoso';

import { type ChunkPage, ragService } from '@/services/rag';

import SkeletonLoading from '../Loading';
import ChunkItem from './ChunkItem';

interface ChunkListProps {
  fileId: string;
}
const ChunkList = memo<ChunkListProps>(({ fileId }) => {
  const { data, isLoading, fetchNextPage } = useInfiniteQuery<ChunkPage>({
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => ragService.getChunksByFileId(fileId, Number(pageParam)),
    queryKey: ['chunks-by-file', fileId],
  });

  const dataSource = data?.pages.flatMap((page) => page.items) || [];

  return isLoading ? (
    <SkeletonLoading />
  ) : (
    <Flexbox flex={1}>
      <Virtuoso
        data={dataSource}
        endReached={() => {
          fetchNextPage();
        }}
        itemContent={(index, item) => (
          <Flexbox key={item.id} paddingInline={12}>
            <ChunkItem {...item} index={index} />
          </Flexbox>
        )}
      />
    </Flexbox>
  );
});

export default ChunkList;
