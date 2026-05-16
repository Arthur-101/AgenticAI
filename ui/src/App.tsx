import { useState } from "react";
import { Button } from "antd";
import { CodeOutlined } from "@ant-design/icons";
import ChatPanel from "./components/ChatPanel";
import TerminalPanel from "./components/TerminalPanel";

function App() {
  const [showTerminal, setShowTerminal] = useState(false);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        <ChatPanel />
        <Button 
          type="primary" 
          icon={<CodeOutlined />} 
          onClick={() => setShowTerminal(!showTerminal)}
          style={{ 
            position: 'absolute', 
            bottom: '20px', 
            right: '20px', 
            zIndex: 1000,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
          }}
        >
          {showTerminal ? 'Hide Terminal' : 'Show Terminal'}
        </Button>
      </div>
      
      {showTerminal && (
        <div style={{ width: '40%', height: '100%', borderLeft: '1px solid #333' }}>
          <TerminalPanel onClose={() => setShowTerminal(false)} />
        </div>
      )}
    </div>
  );
}

export default App;
