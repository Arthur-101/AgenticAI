import React, { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface TerminalPanelProps {
  onClose?: () => void;
}

const TerminalPanel: React.FC<TerminalPanelProps> = ({ onClose }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm
    const term = new Terminal({
      cursorBlink: true,
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
      },
      fontFamily: '"Fira Code", monospace',
      fontSize: 14,
    });
    
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    // Connect to WebSocket
    // Using fixed localhost:8000 since backend runs there
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/terminal`);
    wsRef.current = ws;

    ws.onopen = () => {
      term.writeln('\x1b[32mConnected to AgenticAI Terminal\x1b[0m\r\n');
      
      // Send initial resize
      ws.send(JSON.stringify({
        type: 'resize',
        rows: term.rows,
        cols: term.cols
      }));
    };

    ws.onmessage = (event) => {
      term.write(event.data);
    };

    ws.onerror = (error) => {
      term.writeln('\r\n\x1b[31mTerminal connection error.\x1b[0m\r\n');
      console.error('Terminal WebSocket error:', error);
    };

    ws.onclose = () => {
      term.writeln('\r\n\x1b[33mTerminal connection closed.\x1b[0m\r\n');
    };

    // Handle user input
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }));
      }
    });

    // Handle window resize
    const handleResize = () => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
        if (wsRef.current?.readyState === WebSocket.OPEN && xtermRef.current) {
          wsRef.current.send(JSON.stringify({
            type: 'resize',
            rows: xtermRef.current.rows,
            cols: xtermRef.current.cols
          }));
        }
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (xtermRef.current) {
        xtermRef.current.dispose();
      }
    };
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
      <div 
        ref={terminalRef} 
        style={{ 
          flex: 1, 
          overflow: 'hidden', 
          backgroundColor: '#1e1e1e',
          padding: '8px',
          borderBottomLeftRadius: '8px',
          borderBottomRightRadius: '8px',
        }} 
      />
    </div>
  );
};

export default TerminalPanel;