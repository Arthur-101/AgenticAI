import { Layout, Card, List, Input, Button, Space, message as antdMessage } from 'antd';
import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

const { Header, Content, Footer } = Layout;

export default function ChatPanel() {
  const [messages, setMessages] = useState<Array<{role: string; content: string; model_id?: string}>>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string>('');
  const [backendRunning, setBackendRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize on component mount
  useEffect(() => {
    initializeBackend();
  }, []);

  const initializeBackend = async () => {
    try {
      // Check if backend is already running
      const isRunning = await invoke<boolean>('backend_status');
      setBackendRunning(isRunning);
      
      if (!isRunning) {
        antdMessage.info('Starting AI backend...');
        await invoke('start_backend');
        setBackendRunning(true);
        antdMessage.success('AI backend started');
      }
      
      // Load chat history
      loadChatHistory();
    } catch (error) {
      console.error('Failed to initialize backend:', error);
      antdMessage.error('Failed to start AI backend. Please check Python installation and dependencies.');
    }
  };

  const loadChatHistory = async () => {
    try {
      const history = await invoke<any[]>('get_chat_history', {
        sessionId: sessionId || null,
        limit: 20,
      });
      
      const formattedMessages = history.map(msg => ({
        role: msg.role,
        content: msg.content_raw,
        model_id: msg.model_id,
      }));
      
      setMessages(formattedMessages);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message to backend
      const result = await invoke<{response: string, model: string, session_id: string}>('send_chat_message', {
        message: input,
        sessionId: sessionId || null,
      });
      
      const botMsg = { role: 'assistant', content: result.response, model_id: result.model };
      setMessages(prev => [...prev, botMsg]);
      
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMsg = { role: 'assistant', content: `Error: ${error}` };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Layout style={{ height: '100vh', background: '#f0f2f5' }}>
      <Header style={{ background: '#001529', color: '#fff', textAlign: 'center', padding: '16px 0' }}>
        <h1 style={{ margin: 0 }}>AgenticAI Chat</h1>
      </Header>

      <Content style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: 24 }}>
        <Card className="glass-card" style={{ width: 480, maxHeight: '70vh', overflowY: 'auto', background: 'inherit' }}>
          <List
            itemLayout="vertical"
            dataSource={messages}
            renderItem={msg => (
              <List.Item>
                <div style={{ display: 'flex', marginBottom: 12 }}>
                  <div style={{
                    flexShrink: 0,
                    width: 32,
                    height: 32,
                    borderRadius: 50,
                    background: msg.role === 'user' ? '#1890ff' : '#fafafa',
                    marginRight: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: msg.role === 'user' ? '#fff' : '#666',
                    fontSize: 16,
                  }}>
                    {msg.role === 'user' ? 'U' : 'A'}
                  </div>
                  <div style={{ flex: 1, maxWidth: '75%' }}>
                    <div style={{ 
                      background: msg.role === 'user' ? '#e6f7ff' : '#fff', 
                      borderRadius: 18, 
                      padding: '10px 14px' 
                    }}>
                      {msg.content}
                    </div>
                    {msg.model_id && msg.role === 'assistant' && (
                      <div style={{ fontSize: '10px', color: '#aaa', marginTop: '4px', textAlign: 'right' }}>
                        Model: {msg.model_id}
                      </div>
                    )}
                  </div>
                </div>
              </List.Item>
            )}
          />
        </Card>

        <div style={{ marginLeft: 24, display: 'flex', flexDirection: 'column', width: 280 }}>
          <Button 
            type="primary" 
            block 
            onClick={() => {
              setMessages([]);
              antdMessage.success('Chat cleared');
            }}
          >
            Clear Chat
          </Button>
          
          <Space direction="vertical" style={{ marginTop: 16 }}>
            <Button 
              block 
              type={backendRunning ? 'default' : 'primary'}
              onClick={async () => {
                try {
                  if (backendRunning) {
                    antdMessage.info('Stopping AI backend...');
                    await invoke('stop_backend');
                    setBackendRunning(false);
                    antdMessage.success('AI backend stopped');
                  } else {
                    antdMessage.info('Starting AI backend...');
                    await invoke('start_backend');
                    setBackendRunning(true);
                    antdMessage.success('AI backend started');
                  }
                } catch (error) {
                  antdMessage.error(`Failed: ${error}`);
                }
              }}
            >
              {backendRunning ? 'Stop Agent' : 'Start Agent'}
            </Button>
            
            <Button 
              block 
              onClick={async () => {
                try {
                  const newSessionId = await invoke<string>('new_session');
                  setSessionId(newSessionId);
                  setMessages([]);
                  antdMessage.success('New chat session started');
                } catch (error) {
                  antdMessage.error(`Failed to start new session: ${error}`);
                }
              }}
            >
              New Session
            </Button>
          </Space>
          
          <div style={{ marginTop: 16, padding: 12, background: '#fafafa', borderRadius: 8 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              Session ID:
            </div>
            <div style={{ fontSize: 11, fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {sessionId || 'No active session'}
            </div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
              Status: <span style={{ color: backendRunning ? '#52c41a' : '#ff4d4f' }}>
                {backendRunning ? 'Running' : 'Stopped'}
              </span>
            </div>
          </div>
        </div>
      </Content>

      <Footer style={{ padding: '12px 0', background: '#fff', marginTop: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Input
            placeholder="Type a message..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={sendMessage}
            style={{ width: 300, marginRight: 8 }}
            disabled={!backendRunning || isLoading}
          />
          <Button 
            type="primary" 
            onClick={sendMessage}
            loading={isLoading}
            disabled={!backendRunning || !input.trim()}
          >
            Send
          </Button>
        </div>
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <small>© 2026 AgenticAI • Powered by Tauri + React • {backendRunning ? 'AI Ready' : 'AI Offline'}</small>
        </div>
      </Footer>
    </Layout>
  );
}
