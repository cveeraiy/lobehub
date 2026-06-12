'use client';

import { memo, useEffect } from 'react';

interface ClarityProps {
  projectId?: string;
}

const Clarity = memo<ClarityProps>(({ projectId }) => {
  useEffect(() => {
    if (!projectId) return;

    const script = document.createElement('script');
    script.id = 'clarity-script';
    script.textContent = `
      (function(c,l,a,r,i,t,y){
          c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
      })(window, document, "clarity", "script", "${projectId}");
    `;
    document.head.appendChild(script);
  }, [projectId]);

  return null;
});

export default Clarity;
