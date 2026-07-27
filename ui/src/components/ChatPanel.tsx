import { Layout, List, Input, Button, message as antdMessage, Modal, Popconfirm, Typography, Upload, Select, Collapse, Tooltip, Tag } from 'antd';
import { open } from '@tauri-apps/plugin-dialog';
import { 
  DeleteOutlined, 
  SettingOutlined, 
  EditOutlined, 
  SaveOutlined, 
  PlusOutlined, 
  InboxOutlined, 
  CodeOutlined, 
  CopyOutlined, 
  CheckOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  PoweroffOutlined,
  SendOutlined,
  ClearOutlined,
  PaperClipOutlined
} from '@ant-design/icons';
const { Dragger } = Upload;
import { useState, useEffect, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkEmoji from 'remark-emoji';
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
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [memories, setMemories] = useState<Array<{id: string, role: string, content: string, tags: string[], created_at: string}>>([]);
  const [backendLogs, setBackendLogs] = useState<string[]>([]);
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState('');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // File Attachments & Vector RAG State
  const [attachedFiles, setAttachedFiles] = useState<Array<{ name: string; path: string; chunkCount?: number }>>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processAndIndexFile = async (filePath: string) => {
    const fileName = filePath.split(/[/\\]/).pop() || filePath;
    antdMessage.loading(`Indexing ${fileName} into ChromaDB vector memory...`, 0);
    try {
      const result = await invoke<any>('index_document', { filePath });
      antdMessage.destroy();
      if (result.status === 'success') {
        const newFile = {
          name: fileName,
          path: filePath,
          chunkCount: result.chunk_count
        };
        setAttachedFiles(prev => [...prev.filter(f => f.path !== filePath), newFile]);
        antdMessage.success(`Indexed "${fileName}" into Vector DB (${result.chunk_count} chunks, ${result.character_count} chars)!`);
      } else {
        antdMessage.error(`Failed to index file: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      antdMessage.destroy();
      antdMessage.error(`Error indexing file: ${error}`);
    }
  };

  const handleFileAttach = async () => {
    try {
      const selected = await open({
        multiple: true,
        filters: [{
          name: 'Documents & Code',
          extensions: ['txt', 'py', 'pdf', 'md', 'json', 'csv', 'js', 'ts', 'tsx', 'html', 'css', 'rs', 'log']
        }]
      });

      if (!selected) return;
      const paths = Array.isArray(selected) ? selected : [selected];

      for (const filePath of paths) {
        if (typeof filePath === 'string') {
          await processAndIndexFile(filePath);
        }
      }
    } catch (err) {
      console.warn('Tauri dialog fallback:', err);
      fileInputRef.current?.click();
    }
  };

  const handleHTMLFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const filePath = (file as any).path || file.name;
      await processAndIndexFile(filePath);
    }
  };

  // Collapsible panels state
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  const scrollLogsToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    scrollLogsToBottom();
  }, [backendLogs]);

  // Initialize on component mount
  useEffect(() => {
    initializeBackend();
    
    let unlisten: (() => void) | undefined;
    let isMounted = true;

    listen<string>('backend-log', (event) => {
      if (event.payload.startsWith('SUB_AGENT_MSG:')) {
        try {
          const jsonStr = event.payload.replace('SUB_AGENT_MSG:', '');
          const data = JSON.parse(jsonStr);
          setMessages(prev => [...prev, {
            role: 'sub_agent',
            content: data.content || data.content_raw || data.reply || data.response || jsonStr || '',
            model_id: data.model || data.model_id
          }]);
        } catch (e) {
          console.error("Failed to parse sub agent message", e);
        }
        return;
      }
      
      setBackendLogs(prev => {
        const newLogs = [...prev, event.payload];
        if (newLogs.length > 200) return newLogs.slice(newLogs.length - 200);
        return newLogs;
      });
    }).then(fn => {
      if (!isMounted) {
        fn();
      } else {
        unlisten = fn;
      }
    }).catch(err => console.error("Failed to setup log listener", err));
    
    return () => {
      isMounted = false;
      if (unlisten) unlisten();
    };
  }, []);

  // Reload history when sessionId changes
  useEffect(() => {
    if (sessionId) {
      loadChatHistory();
    }
  }, [sessionId]);

  const initializeBackend = async () => {
    try {
      const isRunning = await invoke<boolean>('backend_status');
      setBackendRunning(isRunning);
      
      if (!isRunning) {
        antdMessage.info('Starting AI backend...');
        await invoke('start_backend');
        setBackendRunning(true);
        antdMessage.success('AI backend started');
      }
      
      await loadSessions();
      await loadChatHistory();
    } catch (error) {
      console.error('Failed to initialize backend:', error);
      antdMessage.error('Failed to start AI backend. Please check Python installation and dependencies.');
    }
  };

  const loadSessions = async () => {
    try {
      const sessionsList = await invoke<any[]>('get_all_sessions');
      setSessions(sessionsList);
      
      if (!sessionId && sessionsList.length > 0) {
        setSessionId(sessionsList[0].session_id);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const loadChatHistory = async () => {
    if (!sessionId) return;
    try {
      const history = await invoke<any[]>('get_chat_history', { sessionId, limit: 100 });
      setMessages(history.map(item => ({
        role: item.role,
        content: item.content || item.content_raw || item.reply || item.response || '',
        model_id: item.model_id
      })));
    } catch (error) {
      console.error('Failed to load chat history:', error);
      antdMessage.error(`Failed to load history: ${error}`);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await invoke<any>('send_chat_message', {
        sessionId: sessionId || 'default',
        message: userMessage,
        model: selectedModel === 'auto' ? null : selectedModel
      });

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.content || response.reply || response.response || (typeof response === 'string' ? response : ''),
        model_id: response.model_id || response.model_used
      }]);
      
      await loadSessions();
    } catch (error) {
      antdMessage.error(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteSession = async (sId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await invoke('delete_session', { sessionId: sId });
      antdMessage.success('Chat deleted');
      if (sId === sessionId) {
        setSessionId('');
        setMessages([]);
      }
      await loadSessions();
    } catch (error) {
      antdMessage.error(`Failed to delete session: ${error}`);
    }
  };

  const loadMemories = async () => {
    try {
      const res = await invoke<any[]>('get_memories');
      setMemories(res);
    } catch (error) {
      console.error('Failed to load memories:', error);
    }
  };

  const handleUpdateMemory = async (id: string) => {
    try {
      await invoke('update_memory', { id, content: editingContent });
      antdMessage.success('Memory updated');
      setEditingMemoryId(null);
      await loadMemories();
    } catch (error) {
      antdMessage.error(`Failed to update memory: ${error}`);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await invoke('delete_memory', { id });
      antdMessage.success('Memory deleted');
      await loadMemories();
    } catch (error) {
      antdMessage.error(`Failed to delete memory: ${error}`);
    }
  };

  return (
    <Layout style={{ height: '100vh', width: '100vw', background: '#0b0f19', color: '#f1f5f9' }}>
      {/* Settings Modal */}
      <Modal
        title="Agent Memories & Persona System"
        open={isSettingsOpen}
        onCancel={() => setIsSettingsOpen(false)}
        footer={null}
        width={700}
      >
        <Typography.Paragraph type="secondary">
          View and edit stored long-term memory entries used for RAG context assembly.
        </Typography.Paragraph>
        <List
          dataSource={memories}
          renderItem={item => (
            <List.Item
              actions={[
                editingMemoryId === item.id ? (
                  <Button icon={<SaveOutlined />} type="link" onClick={() => handleUpdateMemory(item.id)}>Save</Button>
                ) : (
                  <Button icon={<EditOutlined />} type="link" onClick={() => { setEditingMemoryId(item.id); setEditingContent(item.content); }}>Edit</Button>
                ),
                <Popconfirm title="Delete memory?" onConfirm={() => handleDeleteMemory(item.id)}>
                  <Button icon={<DeleteOutlined />} type="link" danger>Delete</Button>
                </Popconfirm>
              ]}
            >
              {editingMemoryId === item.id ? (
                <Input.TextArea 
                  value={editingContent} 
                  onChange={e => setEditingContent(e.target.value)} 
                  autoSize={{ minRows: 2, maxRows: 6 }}
                />
              ) : (
                <div style={{ whiteSpace: 'pre-wrap' }}>{item.content}</div>
              )}
            </List.Item>
          )}
        />
      </Modal>

      {/* Upload Modal */}
      <Modal
        title="Upload Files for Context"
        open={isUploadOpen}
        onCancel={() => setIsUploadOpen(false)}
        footer={null}
        width={600}
      >
        <Typography.Paragraph type="secondary">
          Drag files here or click to browse. The path will be inserted into your prompt.
        </Typography.Paragraph>
        <Dragger
          name="file"
          multiple
          beforeUpload={(file) => {
            const f = file as any;
            const filePath = f.path || f.webkitRelativePath || f.name;
            if (filePath) {
              const formattedPath = filePath.includes(' ') ? `"${filePath}"` : filePath;
              setInput(prev => prev + (prev.trim() ? ' ' : '') + formattedPath + ' ');
              antdMessage.success(`${f.name} path added`);
            } else {
              antdMessage.error("Could not retrieve file path.");
            }
            return false;
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Click or drag file to this area</p>
          <p className="ant-upload-hint">
            Support for code files, PDFs, text, and log files.
          </p>
        </Dragger>
      </Modal>

      {/* Top Application Navigation Header */}
      <Header style={{ 
        background: 'rgba(11, 15, 25, 0.95)', 
        color: '#f8fafc', 
        padding: '0 16px', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(16px)',
        height: '56px',
        flexShrink: 0,
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Tooltip title={leftCollapsed ? "Expand Past Chats" : "Collapse Past Chats"}>
            <Button 
              type="text" 
              icon={leftCollapsed ? <MenuUnfoldOutlined style={{ color: '#38bdf8', fontSize: '18px' }} /> : <MenuFoldOutlined style={{ color: '#94a3b8', fontSize: '18px' }} />} 
              onClick={() => setLeftCollapsed(!leftCollapsed)}
            />
          </Tooltip>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
            <div style={{ 
              width: 32, 
              height: 32, 
              borderRadius: 8, 
              background: 'linear-gradient(135deg, #0284c7, #2563eb)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(37, 99, 235, 0.35)'
            }}>
              <RobotOutlined style={{ color: '#ffffff', fontSize: '18px' }} />
            </div>
            <span>AgenticAI Studio</span>
            <span style={{ 
              fontSize: '11px', 
              fontWeight: 500, 
              padding: '2px 8px', 
              borderRadius: '12px',
              backgroundColor: backendRunning ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: backendRunning ? '#4ade80' : '#f87171',
              border: `1px solid ${backendRunning ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <span className={backendRunning ? "status-dot-pulsing" : ""} style={{ width: 6, height: 6, borderRadius: '50%', background: backendRunning ? '#22c55e' : '#ef4444' }} />
              {backendRunning ? 'Ready' : 'Offline'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Tooltip title="Memory Settings">
            <Button 
              type="text" 
              icon={<SettingOutlined style={{ fontSize: '18px', color: '#94a3b8' }} />} 
              onClick={async () => {
                setIsSettingsOpen(true);
                await loadMemories();
              }}
            />
          </Tooltip>

          <Tooltip title={rightCollapsed ? "Expand Inspector" : "Collapse Inspector"}>
            <Button 
              type="text" 
              icon={rightCollapsed ? <MenuFoldOutlined style={{ color: '#38bdf8', fontSize: '18px' }} /> : <MenuUnfoldOutlined style={{ color: '#94a3b8', fontSize: '18px' }} />} 
              onClick={() => setRightCollapsed(!rightCollapsed)}
            />
          </Tooltip>
        </div>
      </Header>

      {/* Main Studio Workspace Layout */}
      <Layout style={{ flex: 1, overflow: 'hidden', background: '#0b0f19' }}>
        {/* Left Sider: Past Chats */}
        <Sider 
          width={260} 
          collapsible 
          collapsed={leftCollapsed}
          onCollapse={setLeftCollapsed}
          trigger={null}
          collapsedWidth={0} 
          style={{ 
            background: '#070a12', 
            borderRight: '1px solid rgba(255, 255, 255, 0.08)', 
            overflowY: 'auto',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
          }}
        >
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', height: '100%' }}>
            <Button 
              type="primary" 
              block 
              icon={<PlusOutlined />}
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
              style={{
                background: 'linear-gradient(135deg, #2563eb, #0284c7)',
                border: 'none',
                height: '40px',
                borderRadius: '8px',
                fontWeight: 600,
                boxShadow: '0 4px 12px rgba(37, 99, 235, 0.35)'
              }}
            >
              New Chat
            </Button>

            <div style={{ 
              fontSize: '11px', 
              color: '#64748b', 
              textTransform: 'uppercase', 
              fontWeight: 700, 
              letterSpacing: '0.8px',
              marginTop: '4px' 
            }}>
              Past Chats ({sessions.length})
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {sessions.map(item => {
                const isActive = item.session_id === sessionId;
                return (
                  <div 
                    key={item.session_id}
                    onClick={() => {
                      if (item.session_id !== sessionId) {
                        setSessionId(item.session_id);
                      }
                    }}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      background: isActive ? 'rgba(37, 99, 235, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                      border: isActive ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.05)',
                      color: isActive ? '#f8fafc' : '#94a3b8',
                      transition: 'all 0.2s ease',
                      fontSize: '13px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontWeight: isActive ? 600 : 400
                    }}
                    title={item.title}
                  >
                    <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, marginRight: '8px' }}>
                      {item.title || 'Untitled Chat'}
                    </div>
                    <Popconfirm
                      title="Delete session?"
                      onConfirm={(e) => handleDeleteSession(item.session_id, e as React.MouseEvent)}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="Yes"
                      cancelText="No"
                    >
                      <Button 
                        type="text" 
                        danger 
                        icon={<DeleteOutlined />} 
                        size="small" 
                        onClick={(e) => e.stopPropagation()} 
                        style={{ opacity: isActive ? 1 : 0.4, color: '#f87171' }}
                      />
                    </Popconfirm>
                  </div>
                );
              })}
            </div>
          </div>
        </Sider>

        {/* Center: Conversation View */}
        <Layout style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#0b0f19', overflow: 'hidden' }}>
          <Content style={{ flex: 1, padding: '16px 24px', overflowY: 'auto', display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: '100%', maxWidth: '850px', height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
                <List
                  itemLayout="vertical"
                  dataSource={messages}
                  renderItem={msg => (
                    <List.Item style={{ border: 'none', padding: '8px 0' }}>
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                        marginBottom: 12 
                      }}>
                        {msg.role !== 'user' && (
                          <div style={{
                            flexShrink: 0,
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            background: msg.role === 'sub_agent' ? 'linear-gradient(135deg, #a855f7, #6b21a8)' : 'linear-gradient(135deg, #0284c7, #2563eb)',
                            marginRight: 10,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#ffffff',
                            fontSize: 14,
                            boxShadow: '0 4px 10px rgba(0,0,0,0.3)'
                          }}>
                            {msg.role === 'sub_agent' ? '🤖' : 'A'}
                          </div>
                        )}

                        <div style={{ maxWidth: '82%' }}>
                          <div className="chat-markdown-content" style={{ 
                            background: msg.role === 'user' 
                              ? 'linear-gradient(135deg, #2563eb, #1d4ed8)' 
                              : msg.role === 'sub_agent' 
                              ? 'rgba(147, 51, 234, 0.12)' 
                              : 'rgba(255, 255, 255, 0.05)',
                            border: msg.role === 'sub_agent' 
                              ? '1px dashed rgba(168, 85, 247, 0.4)' 
                              : msg.role === 'user' 
                              ? 'none' 
                              : '1px solid rgba(255, 255, 255, 0.08)',
                            color: '#f8fafc',
                            borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px', 
                            padding: '12px 16px',
                            overflowX: 'auto',
                            boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
                            fontSize: '14px',
                            lineHeight: 1.5
                          }}>
                            {(() => {
                              const messageText = msg.content || (msg as any).content_raw || (msg as any).reply || (msg as any).response || '';
                              return msg.role === 'sub_agent' ? (
                                <Collapse 
                                  size="small" 
                                  ghost 
                                  items={[{
                                    key: '1',
                                    label: <span style={{ fontSize: '12px', color: '#c084fc', fontWeight: 600 }}>View Sub-Agent Details ({msg.model_id || 'sub-agent'})</span>,
                                    children: (
                                      <ReactMarkdown 
                                        remarkPlugins={[remarkGfm, remarkEmoji]}
                                        components={{
                                          code({node, inline, className, children, ...props}: any) {
                                            const match = /language-(\w+)/.exec(className || '');
                                            const codeContent = String(children).replace(/\n$/, '');
                                            return !inline && match ? (
                                              <div style={{ position: 'relative' }}>
                                                <Button
                                                  type="text"
                                                  icon={copiedCode === codeContent ? <CheckOutlined style={{ color: '#4ade80' }} /> : <CopyOutlined style={{ color: '#94a3b8' }} />}
                                                  size="small"
                                                  onClick={() => {
                                                    navigator.clipboard.writeText(codeContent);
                                                    setCopiedCode(codeContent);
                                                    setTimeout(() => setCopiedCode(null), 2000);
                                                  }}
                                                  style={{ position: 'absolute', top: 5, right: 5, zIndex: 1, background: 'rgba(15, 23, 42, 0.8)' }}
                                                />
                                                <SyntaxHighlighter
                                                  style={vscDarkPlus as any}
                                                  language={match[1]}
                                                  PreTag="div"
                                                  {...props}
                                                >
                                                  {codeContent}
                                                </SyntaxHighlighter>
                                              </div>
                                            ) : (
                                              <code className={className} style={{background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px', color: '#38bdf8'}} {...props}>
                                                {children}
                                              </code>
                                            );
                                          }
                                        }}
                                      >
                                        {messageText}
                                      </ReactMarkdown>
                                    )
                                  }]} 
                                />
                              ) : (
                                <ReactMarkdown 
                                  remarkPlugins={[remarkGfm, remarkEmoji]}
                                  components={{
                                    code({node, inline, className, children, ...props}: any) {
                                      const match = /language-(\w+)/.exec(className || '');
                                      const codeContent = String(children).replace(/\n$/, '');
                                      return !inline && match ? (
                                        <div style={{ position: 'relative' }}>
                                          <Button
                                            type="text"
                                            icon={copiedCode === codeContent ? <CheckOutlined style={{ color: '#4ade80' }} /> : <CopyOutlined style={{ color: '#94a3b8' }} />}
                                            size="small"
                                            onClick={() => {
                                              navigator.clipboard.writeText(codeContent);
                                              setCopiedCode(codeContent);
                                              setTimeout(() => setCopiedCode(null), 2000);
                                            }}
                                            style={{ position: 'absolute', top: 5, right: 5, zIndex: 1, background: 'rgba(15, 23, 42, 0.8)' }}
                                          />
                                          <SyntaxHighlighter
                                            style={vscDarkPlus as any}
                                            language={match[1]}
                                            PreTag="div"
                                            {...props}
                                          >
                                            {codeContent}
                                          </SyntaxHighlighter>
                                        </div>
                                      ) : (
                                        <code className={className} style={{background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px', color: '#38bdf8'}} {...props}>
                                          {children}
                                        </code>
                                      );
                                    }
                                  }}
                                >
                                  {messageText}
                                </ReactMarkdown>
                              );
                            })()}
                          </div>
                          {(msg.role === 'assistant' || msg.role === 'sub_agent') && (
                            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', textAlign: 'right', display: 'flex', justifyContent: 'flex-end', gap: '8px', alignItems: 'center' }}>
                              {msg.role === 'sub_agent' && (
                                <span style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', padding: '1px 6px', borderRadius: '4px', border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: '10px' }}>
                                  Tool / Sub-Agent
                                </span>
                              )}
                              <span>Model: {msg.model_id || 'qwen/qwen3.5-flash-02-23'}</span>
                            </div>
                          )}
                        </div>

                        {msg.role === 'user' && (
                          <div style={{
                            flexShrink: 0,
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            background: 'linear-gradient(135deg, #0284c7, #3b82f6)',
                            marginLeft: 10,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#ffffff',
                            fontSize: 13,
                            fontWeight: 600
                          }}>
                            U
                          </div>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
                <div ref={messagesEndRef} />
              </div>
            </div>
          </Content>

          {/* Footer Input Toolbar */}
          <Footer style={{ 
            padding: '16px 24px', 
            background: 'rgba(11, 15, 25, 0.95)', 
            borderTop: '1px solid rgba(255, 255, 255, 0.08)', 
            backdropFilter: 'blur(16px)',
            flexShrink: 0 
          }}>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleHTMLFileSelect} 
              style={{ display: 'none' }} 
              multiple 
            />
            {attachedFiles.length > 0 && (
              <div style={{ maxWidth: '850px', margin: '0 auto 8px auto', display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: '#c084fc', fontWeight: 600 }}>
                  📄 Indexed Vector Documents ({attachedFiles.length}):
                </span>
                {attachedFiles.map((file, idx) => (
                  <Tag
                    key={idx}
                    color="purple"
                    closable
                    onClose={() => setAttachedFiles(prev => prev.filter(f => f.path !== file.path))}
                    style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '6px', background: 'rgba(168, 85, 247, 0.15)', border: '1px solid rgba(168, 85, 247, 0.4)', color: '#e9d5ff' }}
                  >
                    {file.name} ({file.chunkCount || 1} chunks)
                  </Tag>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', maxWidth: '850px', margin: '0 auto', gap: '8px' }}>
              <Select
                value={selectedModel}
                onChange={setSelectedModel}
                style={{ width: 170 }}
                disabled={!backendRunning || isLoading}
                options={[
                  { value: 'auto', label: 'Auto (Supervisor)' },
                  { value: 'qwen', label: 'Qwen 3.5 Flash' },
                  { value: 'gemini-flash', label: 'Gemini 2.5 Flash' },
                  { value: 'deepseek', label: 'DeepSeek v3.2' },
                  { value: 'mimo', label: 'MIMO v2 Pro' },
                  { value: 'gemini-pro', label: 'Gemini 3.1 Pro' },
                ]}
              />
              <Tooltip title="Attach Document / Code File (RAG Vector Memory)">
                <Button
                  icon={<PaperClipOutlined />}
                  onClick={handleFileAttach}
                  disabled={!backendRunning || isLoading}
                />
              </Tooltip>
              <Input
                placeholder="Message AgenticAI..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onPressEnter={sendMessage}
                style={{ 
                  flex: 1, 
                  background: 'rgba(255, 255, 255, 0.05)', 
                  border: '1px solid rgba(255, 255, 255, 0.1)', 
                  color: '#f8fafc',
                  borderRadius: '8px'
                }}
                disabled={!backendRunning || isLoading}
              />
              <Button 
                type="primary" 
                icon={<SendOutlined />}
                onClick={sendMessage}
                loading={isLoading}
                disabled={!backendRunning || !input.trim()}
                style={{
                  background: 'linear-gradient(135deg, #2563eb, #0284c7)',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600
                }}
              >
                Send
              </Button>
            </div>
            <div style={{ textAlign: 'center', marginTop: 8, color: '#64748b', fontSize: '11px' }}>
              © 2026 AgenticAI • Multi-Model Agent System • {backendRunning ? 'AI Ready' : 'AI Offline'}
            </div>
          </Footer>
        </Layout>

        {/* Right Sider: Inspector & Agentic Log */}
        <Sider 
          width={320} 
          collapsible 
          collapsed={rightCollapsed}
          onCollapse={setRightCollapsed}
          trigger={null}
          collapsedWidth={0} 
          style={{ 
            background: '#070a12', 
            borderLeft: '1px solid rgba(255, 255, 255, 0.08)', 
            display: 'flex', 
            flexDirection: 'column',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
          }}
        >
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', height: '100%', gap: '16px' }}>
            
            {/* Agent Control Panel */}
            <div style={{ 
              background: 'rgba(255, 255, 255, 0.03)', 
              border: '1px solid rgba(255, 255, 255, 0.08)', 
              borderRadius: '10px', 
              padding: '14px' 
            }}>
              <Button 
                block 
                type="primary"
                icon={<PoweroffOutlined />}
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
                style={{
                  height: '38px',
                  borderRadius: '8px',
                  fontWeight: 600,
                  background: backendRunning 
                    ? 'linear-gradient(135deg, #ef4444, #dc2626)' 
                    : 'linear-gradient(135deg, #22c55e, #16a34a)',
                  border: 'none',
                  boxShadow: backendRunning 
                    ? '0 4px 14px rgba(239, 68, 68, 0.35)' 
                    : '0 4px 14px rgba(34, 197, 94, 0.35)'
                }}
              >
                {backendRunning ? 'Stop Agent Engine' : 'Start Agent Engine'}
              </Button>

              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
                  Session ID
                </div>
                <div style={{ 
                  fontSize: '11px', 
                  fontFamily: '"Fira Code", monospace', 
                  color: '#38bdf8', 
                  background: 'rgba(15, 23, 42, 0.6)', 
                  padding: '6px 8px', 
                  borderRadius: '6px', 
                  border: '1px solid rgba(56, 189, 248, 0.2)',
                  wordBreak: 'break-all',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span>{sessionId ? `${sessionId.slice(0, 18)}...` : 'No active session'}</span>
                  {sessionId && (
                    <Button 
                      type="text" 
                      size="small"
                      icon={<CopyOutlined style={{ color: '#94a3b8', fontSize: '11px' }} />}
                      onClick={() => {
                        navigator.clipboard.writeText(sessionId);
                        antdMessage.success('Session ID copied');
                      }}
                    />
                  )}
                </div>
              </div>
            </div>

            {/* Agentic Log Section */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
              <div style={{ 
                fontSize: '11px', 
                color: '#64748b', 
                marginBottom: '8px', 
                fontWeight: 700, 
                textTransform: 'uppercase', 
                letterSpacing: '0.8px',
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CodeOutlined style={{ color: '#38bdf8' }} />
                  <span>Agent Activity Log</span>
                </div>
                <Button 
                  type="text" 
                  size="small" 
                  icon={<ClearOutlined />}
                  onClick={() => setBackendLogs([])} 
                  style={{ fontSize: '11px', color: '#64748b' }}
                >
                  Clear
                </Button>
              </div>

              <div style={{ 
                flex: 1, 
                background: '#05070f', 
                borderRadius: '8px', 
                padding: '10px', 
                overflowY: 'auto',
                fontFamily: '"Fira Code", "Cascadia Code", monospace',
                fontSize: '11px',
                color: '#cbd5e1',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                border: '1px solid rgba(255, 255, 255, 0.06)'
              }}>
                {backendLogs.length === 0 ? (
                  <div style={{ color: '#475569', fontStyle: 'italic', padding: '10px', textAlign: 'center' }}>
                    System ready. Agent logs will stream here...
                  </div>
                ) : (
                  backendLogs.map((log, i) => {
                    let color = '#cbd5e1';
                    if (log.includes('ERROR') || log.includes('Failed')) color = '#f87171';
                    else if (log.includes('INFO') || log.includes('DEBUG')) color = '#38bdf8';
                    else if (log.includes('SUCCESS') || log.includes('ready')) color = '#4ade80';

                    return (
                      <div key={i} style={{ marginBottom: '4px', borderBottom: '1px solid rgba(255, 255, 255, 0.03)', paddingBottom: '3px', color }}>
                        {log}
                      </div>
                    );
                  })
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </Sider>
      </Layout>
    </Layout>
  );
}
