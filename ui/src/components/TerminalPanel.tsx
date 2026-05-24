import React, { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface TerminalPanelProps {
  onClose?: () => void;
  isVisible?: boolean;
}

const TerminalPanel: React.FC<TerminalPanelProps> = ({ onClose, isVisible = true }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm
    const term = new Terminal({
      cursorBlink: true,
      scrollback: 0, // Disable native scrollback since tmux handles it
      cols: 80,
      rows: 24,
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
      },
      fontFamily: import.meta.env.VITE_TERMINAL_FONT || '"Fira Code", monospace',
      fontSize: 14,
    });
    
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    
    term.open(terminalRef.current);
    if (terminalRef.current.clientWidth > 0) {
      fitAddon.fit();
    }

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    let reconnectTimeoutId: any;
    let isComponentMounted = true;

    const connectWebSocket = () => {
      if (!isComponentMounted) return;
      
      const ws = new WebSocket(`ws://127.0.0.1:8000/ws/terminal`);
      wsRef.current = ws;

      ws.onopen = () => {
        // Send initial resize
        setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN && isComponentMounted && term.cols > 10) {
            ws.send(JSON.stringify({
              type: 'resize',
              rows: term.rows,
              cols: term.cols
            }));
          }
        }, 100);
      };

      ws.onmessage = (event) => {
        term.write(event.data);
      };

      ws.onerror = (error) => {
        console.error('Terminal WebSocket error:', error);
      };

      ws.onclose = () => {
        if (!isComponentMounted) return;
        term.writeln('\r\n\x1b[33mTerminal connection closed. Reconnecting in 2 seconds...\x1b[0m\r\n');
        clearTimeout(reconnectTimeoutId);
        reconnectTimeoutId = setTimeout(connectWebSocket, 2000);
      };
    };

    connectWebSocket();

    // Handle user input
    term.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Handle container resize cleanly using ResizeObserver
    const resizeObserver = new ResizeObserver(() => {
      if (fitAddonRef.current && terminalRef.current && terminalRef.current.clientWidth > 0) {
        fitAddonRef.current.fit();
        if (wsRef.current?.readyState === WebSocket.OPEN && xtermRef.current) {
          wsRef.current.send(JSON.stringify({
            type: 'resize',
            rows: xtermRef.current.rows,
            cols: xtermRef.current.cols
          }));
        }
      }
    });

    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current);
    }

    return () => {
      isComponentMounted = false;
      resizeObserver.disconnect();
      clearTimeout(reconnectTimeoutId);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect loop on unmount
        wsRef.current.close();
      }
      if (xtermRef.current) {
        xtermRef.current.dispose();
      }
    };
  }, []);

  useEffect(() => {
    if (fitAddonRef.current && terminalRef.current) {
      if (terminalRef.current.clientWidth > 0) {
        fitAddonRef.current.fit();
      }
    }
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        padding: '8px 16px', 
        backgroundColor: '#2d2d2d',
        color: '#fff',
        borderTopLeftRadius: '8px',
        borderTopRightRadius: '8px',
        borderBottom: '1px solid #444'
      }}>
        <div style={{ fontWeight: 'bold' }}>AgenticAI Shared Terminal</div>
        {onClose && (
          <button 
            onClick={onClose}
            style={{ 
              background: 'none', 
              border: 'none', 
              color: '#fff', 
              cursor: 'pointer',
              fontSize: '16px' 
            }}
          >
            ×
          </button>
        )}
      </div>
      <div style={{ 
        flex: 1, 
        backgroundColor: '#1e1e1e',
        padding: '8px',
        borderBottomLeftRadius: '8px',
        borderBottomRightRadius: '8px',
        height: '0px', // Force flex: 1 to dictate height, not content
        overflow: 'hidden'
      }}>
        <div 
          ref={terminalRef} 
          style={{ 
            width: '100%',
            height: '100%',
          }} 
        />
      </div>
    </div>
  );
};

export default TerminalPanel;