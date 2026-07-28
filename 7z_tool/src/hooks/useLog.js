import { useState, useRef, useCallback } from 'react';

export function useLog() {
  const [logText, setLogText] = useState('');
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef(null);

  const log = useCallback((msg) => {
    setLogText(prev => prev + msg + '\n');
    setShowLog(true);
    setTimeout(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, 50);
  }, []);

  const resetLog = useCallback(() => {
    setLogText('');
    setShowLog(false);
  }, []);

  return { logText, showLog, logRef, log, resetLog };
}
