import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

import { isTestEnv } from '../../lib/env';

const EASE = [0.16, 1, 0.3, 1] as const;

/**
 * Cinematic cross-route transition. Renders a plain fragment in test
 * environments to keep the DOM free of motion wrappers.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  if (isTestEnv()) return <>{children}</>;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.35, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}