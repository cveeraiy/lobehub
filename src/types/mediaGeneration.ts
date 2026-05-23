export interface CreateImageServicePayload {
  generationTopicId: string;
  imageNum: number;
  model: string;
  params: {
    cfg?: number;
    height?: number;
    imageUrls?: string[];
    prompt: string;
    seed?: null | number;
    steps?: number;
    width?: number;
    [key: string]: unknown;
  };
  provider: string;
}

export interface CreateVideoServicePayload {
  generationTopicId: string;
  model: string;
  params: {
    aspectRatio?: string;
    cameraFixed?: boolean;
    duration?: number;
    endImageUrl?: null | string;
    generateAudio?: boolean;
    imageUrl?: null | string;
    prompt: string;
    resolution?: string;
    seed?: null | number;
    [key: string]: unknown;
  };
  provider: string;
}

export interface UpdateGenerationTopicValue {
  coverUrl?: null | string;
  title?: null | string;
}
