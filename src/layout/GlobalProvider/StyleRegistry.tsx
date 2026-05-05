'use client';

import { StyleProvider } from 'antd-style';
import { type PropsWithChildren, useEffect } from 'react';

const StyleRegistry = ({ children }: PropsWithChildren) => {
  useEffect(() => {
    const id = 'style-registry-base';
    if (document.getElementById(id)) return;

    const style = document.createElement('style');
    style.id = id;
    style.textContent = `
      html body { background: #f8f8f8; }
      html[data-theme="dark"] body { background-color: #000; }
    `;
    document.head.appendChild(style);
  }, []);

  return <StyleProvider>{children}</StyleProvider>;
};

export default StyleRegistry;
