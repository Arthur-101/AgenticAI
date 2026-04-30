import { Layout, Card, List, Input, Button, Space, message as antdMessage } from 'antd';
import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const { Header, Content, Footer, Sider } = Layout;

export default function ChatPanel() {
  const [messages, setMessages] = useState<Array<{role: string; content: string; model_id?: string}>>([]);
  const [sessions, setSessions] = useState<Array<{session_id: string; title: string; created_at: string}>>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string>('');
  const [backendRunning, setBackendRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize on component mount
  useEffect(() => {
    initializeBackend();
  }, []);

  // Reload history when sessionId changes
  useEffect(() => {
    if (sessionId) {
      loadChatHistory();
    }
  }, [sessionId]);

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
      
      // Load sessions and chat history
      await loadSessions();
      await loadChatHistory();
    } catch (error) {
      console.error('Failed to initialize backend:', error);
      antdMessage.error('Failed to start AI backend. Please check Python installation and dependencies.');
    }
  };

  const loadSessions = async () => {
    try {
      if (!backendRunning) return; // Prevent loading if backend is not ready
      const sessionsList = await invoke<any[]>('get_all_sessions');
      setSessions(sessionsList);
      
      // If we don't have an active session but we have history, load the most recent one
      if (!sessionId && sessionsList.length > 0) {
        setSessionId(sessionsList[0].session_id);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const loadChatHistory = async () => {
    try {
      if (!backendRunning) return;
      const history = await invoke<any[]>('get_chat_history', {
        sessionId: sessionId || null,
        limit: 50,
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
      
      // If this was the first message, the backend might have auto-created a session
      // Let's reload sessions so it appears in the sidebar
      if (!sessionId && result.session_id) {
        setSessionId(result.session_id);
      }
      await loadSessions();
      
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

      <Layout hasSider style={{ background: 'inherit' }}>
        <Sider width={250} style={{ background: '#fff', borderRight: '1px solid #f0f0f0', overflowY: 'auto' }}>
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Button 
              type="primary" 
              block 
              onClick={async () => {
                try {
                  const newSessionId = await invoke<string>('new_session');
                  setSessionId(newSessionId);
                  setMessages([]);
                  await loadSessions();
                  antdMessage.success('New chat session started');
                } catch (error) {
                  antdMessage.error(`Failed to start new session: ${error}`);
                }
              }}
            >
              + New Chat
            </Button>
            <div style={{ marginTop: '12px', fontSize: '12px', color: '#999', textTransform: 'uppercase', fontWeight: 'bold' }}>
              Past Chats
            </div>
            <List
              dataSource={sessions}
              renderItem={item => (
                <div 
                  onClick={() => {
                    if (item.session_id !== sessionId) {
                      setSessionId(item.session_id);
                    }
                  }}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: item.session_id === sessionId ? '#e6f7ff' : 'transparent',
                    border: item.session_id === sessionId ? '1px solid #91d5ff' : '1px solid transparent',
                    transition: 'all 0.2s',
                    marginBottom: '4px',
                    fontSize: '14px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}
                  title={item.title}
                >
                  {item.title || 'Empty Chat'}
                </div>
              )}
            />
          </div>
        </Sider>

        <Layout style={{ background: 'inherit' }}>
          <Content style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: 24, overflow: 'hidden' }}>
            <Card className="glass-card" style={{ flex: 1, maxWidth: '800px', height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column', background: 'inherit' }}>
              <div style={{ flex: 1, overflowY: 'auto', paddingRight: '12px' }}>
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
                        <div style={{ flex: 1, maxWidth: '85%' }}>
                          <div style={{ 
                            background: msg.role === 'user' ? '#e6f7ff' : '#fff', 
                            borderRadius: 18, 
                            padding: '10px 14px',
                            overflowX: 'auto'
                          }}>
                            <ReactMarkdown 
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code({node, inline, className, children, ...props}: any) {
                                  const match = /language-(\w+)/.exec(className || '');
                                  return !inline && match ? (
                                    <SyntaxHighlighter
                                      style={vscDarkPlus as any}
                                      language={match[1]}
                                      PreTag="div"
                                      {...props}
                                    >
                                      {String(children).replace(/\n$/, '')}
                                    </SyntaxHighlighter>
                                  ) : (
                                    <code className={className} style={{background: '#f0f0f0', padding: '2px 4px', borderRadius: '4px'}} {...props}>
                                      {children}
                                    </code>
                                  );
                                }
                              }}
                            >
                              {msg.content}
                            </ReactMarkdown>
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
              </div>
            </Card>

            <div style={{ marginLeft: 24, display: 'flex', flexDirection: 'column', width: 280 }}>
              <Space direction="vertical" style={{ marginTop: 0 }}>
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

          <Footer style={{ padding: '12px 24px', background: '#fff', marginTop: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', maxWidth: '800px', margin: '0 auto' }}>
              <Input
                placeholder="Type a message..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onPressEnter={sendMessage}
                style={{ flex: 1, marginRight: 8 }}
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
              <small>© 2026 AgenticAI • Powered by Tauri + React • {backendRunning ? 'AI Ready' : 'AI Offline'}</small>
            </div>
          </Footer>
        </Layout>
      </Layout>
    </Layout>
  );
}
