import { UAParser } from 'ua-parser-js';

/**
 * check mobile device in server
 */
export const isMobileDevice = (request: Request) => {
  const ua = request.headers.get('user-agent');
  const device = new UAParser(ua || '').getDevice();

  return device.type === 'mobile';
};

/**
 * check mobile device in server
 */
export const gerServerDeviceInfo = (request: Request) => {
  const ua = request.headers.get('user-agent');
  const parser = new UAParser(ua || '');

  return {
    browser: parser.getBrowser().name,
    isMobile: isMobileDevice(request),
    os: parser.getOS().name,
  };
};
