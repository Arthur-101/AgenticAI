import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Rnd } from 'react-rnd';
import { 
  CodeOutlined, 
  FullscreenOutlined, 
  FullscreenExitOutlined, 
  ClearOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import { Tooltip } from 'antd';
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

  const [isMaximized, setIsMaximized] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm with a sleek dark theme
    const term = new Terminal({
      cursorBlink: true,
      scrollback: 1000,
      cols: 80,
      rows: 24,
      theme: {
        background: '#0b0f19',
        foreground: '#e2e8f0',
        cursor: '#38bdf8',
        cursorAccent: '#0b0f19',
        selectionBackground: 'rgba(56, 189, 248, 0.3)',
        black: '#0f172a',
        red: '#f87171',
        green: '#4ade80',
        yellow: '#fbbf24',
        blue: '#60a5fa',
        magenta: '#c084fc',
        cyan: '#38bdf8',
        white: '#f1f5f9',
        brightBlack: '#475569',
        brightRed: '#ef4444',
        brightGreen: '#22c55e',
        brightYellow: '#eab308',
        brightBlue: '#3b82f6',
        brightMagenta: '#a855f7',
        brightCyan: '#06b6d4',
        brightWhite: '#ffffff',
      },
      fontFamily: import.meta.env.VITE_TERMINAL_FONT || 'Consolas, "Cascadia Code", "Fira Code", "Courier New", monospace',
      fontSize: 14,
      fontWeight: 'normal',
      letterSpacing: 0,
      lineHeight: 1.1,
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
        setIsConnected(true);
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
        setIsConnected(false);
      };

      ws.onclose = () => {
        if (!isComponentMounted) return;
        setIsConnected(false);
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
      if (terminalRef.current.parentElement) {
        resizeObserver.observe(terminalRef.current.parentElement);
      }
    }

    return () => {
      isComponentMounted = false;
      resizeObserver.disconnect();
      clearTimeout(reconnectTimeoutId);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      if (xtermRef.current) {
        xtermRef.current.dispose();
      }
    };
  }, []);

  useEffect(() => {
    if (isVisible && fitAddonRef.current && terminalRef.current) {
      setTimeout(() => {
        if (terminalRef.current && terminalRef.current.clientWidth > 0) {
          fitAddonRef.current?.fit();
        }
      }, 50);
    }
  }, [isVisible, isMaximized]);

  const handleClear = () => {
    xtermRef.current?.clear();
  };

  const toggleMaximize = () => {
    setIsMaximized(!isMaximized);
  };

  const defaultWidth = Math.min(950, window.innerWidth - 60);
  const defaultHeight = Math.min(600, window.innerHeight - 100);

  const rndPositionProps = isMaximized
    ? {
        position: { x: 0, y: 0 },
        size: { width: '100vw', height: '100vh' },
        disableDragging: true,
        enableResizing: false,
      }
    : {
        default: {
          x: Math.max(window.innerWidth / 2 - defaultWidth / 2, 20),
          y: Math.max(window.innerHeight / 2 - defaultHeight / 2, 20),
          width: defaultWidth,
          height: defaultHeight,
        },
        minWidth: 400,
        minHeight: 250,
        bounds: "window",
        dragHandleClassName: "terminal-drag-handle",
      };

  return (
    <Rnd
      {...rndPositionProps}
      style={{ zIndex: 2000 }}
    >
      <div className="terminal-window-container">
        {/* Modern Window Header Bar */}
        <div className="terminal-drag-handle terminal-window-header">
          {/* Left: macOS dots & Title */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <button 
                className="mac-dot mac-dot-close" 
                onClick={onClose} 
                title="Hide Terminal"
              />
              <button 
                className="mac-dot mac-dot-minimize" 
                onClick={onClose} 
                title="Minimize Terminal"
              />
              <button 
                className="mac-dot mac-dot-maximize" 
                onClick={toggleMaximize} 
                title={isMaximized ? "Restore Window" : "Maximize Window"}
              />
            </div>

            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              fontSize: '13px', 
              fontWeight: 600, 
              color: '#f8fafc',
              marginLeft: '4px'
            }}>
              <CodeOutlined style={{ color: '#38bdf8', fontSize: '15px' }} />
              <span>AgenticAI Terminal</span>
              <span style={{ 
                display: 'inline-flex', 
                alignItems: 'center', 
                gap: '5px',
                fontSize: '11px',
                fontWeight: 500,
                color: isConnected ? '#4ade80' : '#f59e0b',
                backgroundColor: isConnected ? 'rgba(34, 197, 94, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                padding: '2px 8px',
                borderRadius: '12px',
                marginLeft: '6px'
              }}>
                <span className={isConnected ? "status-dot-pulsing" : ""} style={{ width: 6, height: 6, borderRadius: '50%', background: isConnected ? '#22c55e' : '#f59e0b' }} />
                {isConnected ? 'Live' : 'Connecting'}
              </span>
            </div>
          </div>

          {/* Right: Header Control Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Tooltip title="Clear Terminal Screen">
              <button className="terminal-header-btn" onClick={handleClear}>
                <ClearOutlined />
                <span>Clear</span>
              </button>
            </Tooltip>

            <Tooltip title={isMaximized ? "Restore Window Size" : "Maximize Window"}>
              <button className="terminal-header-btn" onClick={toggleMaximize}>
                {isMaximized ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              </button>
            </Tooltip>

            {onClose && (
              <Tooltip title="Hide Terminal (Esc)">
                <button className="terminal-header-btn terminal-header-btn-close" onClick={onClose}>
                  <EyeInvisibleOutlined />
                  <span>Hide Terminal</span>
                </button>
              </Tooltip>
            )}
          </div>
        </div>

        {/* Terminal Body */}
        <div style={{ 
          flex: 1, 
          backgroundColor: '#0b0f19',
          padding: '6px 8px',
          position: 'relative',
          minHeight: 0
        }}>
          <div 
            style={{
              position: 'absolute',
              top: '6px',
              bottom: '6px',
              left: '8px',
              right: '8px'
            }}
          >
            <div 
              ref={terminalRef} 
              style={{ 
                width: '100%',
                height: '100%',
                overflow: 'hidden', 
              }} 
            />
          </div>
        </div>
      </div>
    </Rnd>
  );
};

export default TerminalPanel;