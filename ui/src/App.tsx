import { useState, useEffect } from "react";
import { CodeOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import ChatPanel from "./components/ChatPanel";
import TerminalPanel from "./components/TerminalPanel";

function App() {
  const [showTerminal, setShowTerminal] = useState(false);

  // Allow Esc key to close terminal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showTerminal) {
        setShowTerminal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showTerminal]);

  return (
    <div style={{ position: 'relative', display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', backgroundColor: '#0f172a' }}>
      <div style={{ flex: 1, height: '100%', width: '100%', position: 'relative' }}>
        <ChatPanel />
        
        {/* Floating Circular Terminal Icon Button */}
        <Tooltip title={showTerminal ? "Hide Stateful Terminal (Esc)" : "Open Stateful Terminal"} placement="left">
          <button 
            onClick={() => setShowTerminal(!showTerminal)}
            style={{ 
              position: 'absolute', 
              bottom: '24px', 
              right: '24px', 
              zIndex: 1000,
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: showTerminal 
                ? 'linear-gradient(135deg, #ef4444, #dc2626)' 
                : 'linear-gradient(135deg, #2563eb, #0284c7)',
              color: '#ffffff',
              border: '1px solid rgba(255, 255, 255, 0.25)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: showTerminal 
                ? '0 8px 24px rgba(239, 68, 68, 0.45)' 
                : '0 8px 24px rgba(37, 99, 235, 0.45)',
              backdropFilter: 'blur(12px)',
              transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: 'translateY(0)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px) scale(1.08)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0) scale(1)';
            }}
          >
            <CodeOutlined style={{ fontSize: '20px' }} />
          </button>
        </Tooltip>
      </div>
      
      <div style={{ display: showTerminal ? 'block' : 'none' }}>
        <TerminalPanel onClose={() => setShowTerminal(false)} isVisible={showTerminal} />
      </div>
    </div>
  );
}

export default App;
