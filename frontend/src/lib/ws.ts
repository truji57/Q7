import { useEffect, useRef, useCallback } from 'react';

export function useWebSocket(onMessage: (data: any) => void, onDisconnect?: () => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    // Clean up old socket
    if (wsRef.current) {
      try { wsRef.current.onclose = null; wsRef.current.close(); } catch {}
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
      ws.send('ping');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {}
    };

    ws.onclose = () => {
      onDisconnect?.();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      reconnectRef.current = setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
