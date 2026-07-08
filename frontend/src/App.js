import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';
import { AuthProvider, useAuth, authHeaders } from './AuthContext';

const API_BASE = (
  window.location.hostname === 'localhost'
    ? 'http://127.0.0.1:8000'
    : process.env.REACT_APP_API_URL || ''
);

async function requestJson(url, options = {}) {
  const res = await fetch(url, options);
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = { detail: raw || 'Unknown response format' };
  }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message || data.error)) || `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

/* ---- Toast System ---- */
const ToastContext = React.createContext();
function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const add = useCallback((msg, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t));
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 300);
    }, duration);
  }, []);
  const remove = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, removing: true } : t));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 300);
  }, []);
  return (
    <ToastContext.Provider value={add}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}${t.removing ? ' removing' : ''}`} onClick={() => remove(t.id)}>
            <span className="toast-icon">
              {t.type === 'success' ? '#' : t.type === 'error' ? '!' : 'i'}
            </span>
            <span className="toast-msg">{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
function useToast() { return React.useContext(ToastContext); }

function EmptyState({ icon, title, desc }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          {icon || <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>}
        </svg>
      </div>
      <span className="empty-state-title">{title || 'Nothing here'}</span>
      {desc && <span className="empty-state-desc">{desc}</span>}
    </div>
  );
}

function AuthButton() {
  const { user, loading, signOut, promptGoogleSignIn } = useAuth();

  if (loading) return <div className="auth-btn-placeholder" />;
  if (user) {
    return (
      <div className="auth-user" title={user.email}>
        {user.picture && <img src={user.picture} alt="" className="auth-avatar" referrerPolicy="no-referrer" />}
        <span className="auth-name">{user.name}</span>
        <button className="ghost-btn small" onClick={signOut}>Sign out</button>
      </div>
    );
  }
  return (
    <div className="auth-google-btn">
      <button className="ghost-btn" onClick={promptGoogleSignIn}>Sign in with Google</button>
    </div>
  );
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function ConversationsPanel({ activeConv, onSelect, onNew, repoUrl }) {
  const { user, token } = useAuth();
  const [convs, setConvs] = useState([]);

  const fetchConvs = useCallback(async () => {
    if (!user) { setConvs([]); return; }
    try {
      const data = await requestJson(`${API_BASE}/conversations/`, { headers: authHeaders(token) });
      setConvs(data);
    } catch { setConvs([]); }
  }, [user, token]);

  useEffect(() => { fetchConvs(); }, [fetchConvs]);

  const delConv = async (id) => {
    try {
      await requestJson(`${API_BASE}/conversations/${id}`, { method: 'DELETE', headers: authHeaders(token) });
      if (activeConv === id) onSelect(null);
      fetchConvs();
    } catch { }
  };

  const filteredConvs = useMemo(() => {
    return repoUrl ? convs.filter((c) => c.repo_url === repoUrl) : convs;
  }, [convs, repoUrl]);

  if (!user) return null;

  return (
    <div className="conv-panel">
      <div className="conv-header">
        <span className="conv-title-label">Conversations</span>
        <button className="ghost-btn small" disabled={!repoUrl} title={repoUrl ? '' : 'Ingest a repo first'} onClick={async () => {
          try {
            const headers = { ...authHeaders(token), 'Content-Type': 'application/json' };
            const body = repoUrl ? { repo_url: repoUrl } : {};
            const data = await requestJson(`${API_BASE}/conversations/`, { method: 'POST', headers, body: JSON.stringify(body) });
            onSelect(data.id);
            fetchConvs();
          } catch { }
        }}>New</button>
      </div>
      {repoUrl && <div className="conv-repo-label">{repoUrl.replace('https://github.com/', '')}</div>}
      <div className="conv-list">
        {filteredConvs.length === 0 && <span className="conv-empty">{repoUrl ? 'No conversations for this repo' : 'No conversations yet'}</span>}
        {filteredConvs.map((c) => (
          <div key={c.id} className={`conv-item ${activeConv === c.id ? 'active' : ''}`} onClick={() => onSelect(c.id)}>
            <span className="conv-title">{c.title}</span>
            <span className="conv-time">{timeAgo(c.updated_at || c.created_at)}</span>
            <button className="conv-del" onClick={(e) => { e.stopPropagation(); delConv(c.id); }} title="Delete">&times;</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function IngestResult({ data, loading }) {
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 0' }}>
        <div className="progress-wrap">
          <div className="progress-bar indeterminate" />
        </div>
        <span className="progress-label">Fetching files via GitHub API... (may take a while on large repos)</span>
      </div>
    );
  }
  if (!data) return null;
  if (data.error) return <div className="status-badge error">{data.error}</div>;
  return (
    <div className="stats-grid">
      <div className="stat-box"><span>Repository</span><strong>{data.repo || '-'}</strong></div>
      <div className="stat-box"><span>Files</span><strong>{data.files_ingested ?? 0}</strong></div>
      <div className="stat-box"><span>Chunks</span><strong>{data.chunks_ingested ?? 0}</strong></div>
      <div className="stat-box"><span>Sample</span><strong>{data.sample_file || '-'}</strong></div>
    </div>
  );
}

function SearchResult({ data, loading }) {
  if (loading) {
    return (
      <div className="result-list">
        {[1,2,3].map(i => (
          <div key={i} className="chunk-card" style={{ borderLeftColor: 'var(--border-subtle)' }}>
            <div className="chunk-meta"><span className="skeleton text" style={{ width: 40 }} /><span className="skeleton text" style={{ width: 60 }} /></div>
            <div className="skeleton text" style={{ width: '70%' }} />
            <div className="skeleton card" />
          </div>
        ))}
      </div>
    );
  }
  if (!data) return <EmptyState icon={<><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>} title="Search your codebase" desc="Enter a query above to find semantically relevant code." />;
  if (data.error) return <div className="status-badge error">{data.error}</div>;
  if (!Array.isArray(data.results) || data.results.length === 0)
    return <EmptyState icon={<><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>} title="No results found" desc="Try rephrasing your query or ingesting more files." />;
  return (
    <div className="result-list">
      {data.results.map((item) => {
        const path = item.metadata?.path || '';
        const ext = path.split('.').pop().toLowerCase();
        const isMarkdown = ext === 'md';
        const renderContent = isMarkdown ? item.chunk : `\`\`\`${ext}\n${item.chunk}\n\`\`\``;

        return (
          <div className="chunk-card" key={`${item.rank}-${item.metadata?.chunk_id || item.score}`}>
            <div className="chunk-meta">
              <span className="chunk-rank">#{item.rank}</span>
              <span className="chunk-score">{Number(item.score).toFixed(3)}</span>
            </div>
            <p className="chunk-path">{path || 'unknown'}</p>
            <div className="chunk-code">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{renderContent}</ReactMarkdown>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GptResult({ data, loading, hideAnswer }) {
  if (loading) {
    return (
      <div className="qa-result">
        <div className="answer-box" style={{ borderTopColor: 'var(--border-subtle)' }}>
          <div className="answer-top"><span className="skeleton text" style={{ width: 80 }} /><span className="skeleton text" style={{ width: 100 }} /></div>
          <div className="skeleton title" style={{ width: '90%' }} />
          <div className="skeleton text" style={{ width: '70%' }} />
          <div className="skeleton text" style={{ width: '50%' }} />
        </div>
      </div>
    );
  }
  if (!data) return <EmptyState icon={<><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></>} title="Ask a question" desc="Type a question above and get a grounded answer from your codebase." />;
  if (data.error) return <div className="status-badge error">{data.error}</div>;
  const isLow = data.confidence === 'low';
  return (
    <div className="qa-result">
      {!hideAnswer && (
        <div className={`answer-box ${isLow ? 'low' : ''}`}>
          <div className="answer-top">
            <span className="answer-lbl">Answer</span>
            {data.confidence && (
              <span className={`conf-badge ${data.confidence}`}>
                {data.confidence} &middot; {(data.confidence_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <div className="answer-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.result || 'No answer'}</ReactMarkdown>
          </div>
        </div>
      )}
      {Array.isArray(data.context) && data.context.length > 0 && (
        <div className="ctx-section">
          <p className="ctx-heading">Context ({data.context.length})</p>
          {data.context.map((ctx, i) => (
            <div className="chunk-card" key={i}>
              <p className="chunk-path">{ctx.metadata?.path || ctx.source || 'unknown'}</p>
              <pre className="chunk-code">{ctx.chunk}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArchitecturePanel() {
  const toast = useToast();
  const [diagram, setDiagram] = useState(null);
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);
  const [mermaidLoaded, setMermaidLoaded] = useState(false);

  useEffect(() => {
    if (window.mermaid) {
      window.mermaid.initialize({ startOnLoad: false, theme: 'dark', htmlLabels: false, flowchart: { useMaxWidth: false, htmlLabels: false, nodeSpacing: 80, rankSpacing: 100 }, themeVariables: { primaryColor: '#1e1e3a', primaryTextColor: '#c4c4d8', primaryBorderColor: '#3a3a5a', lineColor: '#6366f1', secondaryColor: '#12122a', tertiaryColor: '#0a0a18', fontSize: '18px' } });
      setMermaidLoaded(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
    script.onload = () => {
      window.mermaid.initialize({ startOnLoad: false, theme: 'dark', htmlLabels: false, flowchart: { useMaxWidth: false, htmlLabels: false, nodeSpacing: 80, rankSpacing: 100 }, themeVariables: { primaryColor: '#1e1e3a', primaryTextColor: '#c4c4d8', primaryBorderColor: '#3a3a5a', lineColor: '#6366f1', secondaryColor: '#12122a', tertiaryColor: '#0a0a18', fontSize: '18px' } });
      setMermaidLoaded(true);
    };
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!diagram || !mermaidLoaded || !containerRef.current) return;
    const h = containerRef.current;
    h.innerHTML = '';
    const pre = document.createElement('div');
    pre.className = 'mermaid';
    pre.textContent = diagram;
    h.appendChild(pre);
    window.mermaid.run({ nodes: [pre] }).then(() => {
      if (h.querySelector('.mermaid svg') === null && h.textContent.includes('Syntax error')) {
        console.error('Mermaid syntax error in diagram source');
        h.innerHTML = '<p class="hint">Could not render diagram</p>';
      }
    }).catch((err) => {
      console.error('Mermaid render error:', err);
      h.innerHTML = '<p class="hint">Could not render diagram</p>';
    });
  }, [diagram, mermaidLoaded]);

  const generate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDiagram(null);
    setInfo(null);
    try {
      const res = await requestJson(`${API_BASE}/architecture/generate`, { method: 'POST' });
      setDiagram(res.mermaid);
      setInfo(res);
      toast(`Architecture generated (${res.modules_found ?? 0} modules)`, 'success');
    } catch (err) {
      setError(err.message);
      toast(`Architecture generation failed: ${err.message}`, 'error', 6000);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div>
      <button className="primary-btn" onClick={generate} disabled={loading} style={{ marginBottom: 14 }}>
        {loading ? 'Analyzing...' : 'Generate'}
      </button>
      {error && <div className="status-badge error" style={{ marginBottom: 10 }}>{error}</div>}
      {loading && <p className="hint">Analyzing project structure and detecting modules...</p>}

      {info && (
        <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {info.layers && (
            <div>
              <p className="ctx-heading">Layers</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(info.layers).map(([layer, modules]) =>
                  modules.length > 0 && (
                    <span key={layer} className="flow-step" style={{ textTransform: 'capitalize' }}>
                      {layer} ({modules.length})
                    </span>
                  )
                )}
              </div>
            </div>
          )}
          {info.entry_points && info.entry_points.length > 0 && (
            <div>
              <p className="ctx-heading">Entry Points</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {info.entry_points.map((ep) => (
                  <span key={ep} className="flow-step" style={{ borderColor: '#34d399' }}>
                    {ep.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                ))}
              </div>
            </div>
          )}
          {info.tech && (
            <div>
              <p className="ctx-heading">Technology Stack</p>
              <div className="stats-grid">
                {Object.entries(info.tech).map(([layer, items]) => (
                  <div className="stat-box" key={layer}>
                    <span style={{ textTransform: 'capitalize' }}>{layer}</span>
                    <strong>{(Array.isArray(items) ? items : [items]).join(', ')}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className="hint" style={{ fontSize: '0.72rem' }}>
            {info.modules_found} modules &middot; {info.dependencies || 0} dependencies
          </p>
        </div>
      )}

      <div ref={containerRef} className="mermaid-container" />
    </div>
  );
}

const NavIcon = ({ name }) => {
  const paths = {
    ingest: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
    search: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
    qa: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
    tree: 'M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z',
  };
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name]} />
    </svg>
  );
};

function AppInner() {
  const { user, token } = useAuth();
  const toast = useToast();
  const [page, setPage] = useState('home');
  const [tab, setTab] = useState('ingest');
  const [repoUrl, setRepoUrl] = useState('');
  const [maxFiles, setMaxFiles] = useState(500);
  const [query, setQuery] = useState('');
  const [gptPrompt, setGptPrompt] = useState('');
  const [topK] = useState(3);
  const [loading, setLoading] = useState({ ingest: false, query: false, gpt: false });
  const [results, setResults] = useState({ ingest: null, query: null, gpt: null });
  const [activeConv, setActiveConv] = useState(null);
  const [convData, setConvData] = useState(null);
  const [convRefreshKey, setConvRefreshKey] = useState(0);

  const fetchConversation = useCallback(async (convId) => {
    if (!convId || !token) { setConvData(null); return; }
    try {
      const data = await requestJson(`${API_BASE}/conversations/${convId}`, { headers: authHeaders(token) });
      setConvData(data);
    } catch { setConvData(null); }
  }, [token]);

  useEffect(() => { fetchConversation(activeConv); }, [activeConv, fetchConversation]);

  const isValidUrl = useMemo(() => {
    try { return !!new URL(repoUrl.trim()); }
    catch { return false; }
  }, [repoUrl]);

  const handleIngest = async () => {
    if (!repoUrl.trim()) return;
    setLoading(s => ({ ...s, ingest: true }));
    try {
      const data = await requestJson(`${API_BASE}/github/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl.trim(), max_files: Number(maxFiles) }),
      });
      setResults(s => ({ ...s, ingest: data }));
      toast(`Ingested ${data.files_ingested ?? 0} files from ${data.repo || 'repo'}`, 'success');
    } catch (err) {
      setResults(s => ({ ...s, ingest: { error: `Ingest failed: ${err.message}` } }));
      toast(`Ingest failed: ${err.message}`, 'error');
    } finally {
      setLoading(s => ({ ...s, ingest: false }));
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(s => ({ ...s, query: true }));
    try {
      const data = await requestJson(`${API_BASE}/query/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), top_k: Number(topK) }),
      });
      setResults(s => ({ ...s, query: data }));
      if (data.results?.length) toast(`Found ${data.results.length} results`, 'success');
      else toast('No results found', 'info');
    } catch (err) {
      setResults(s => ({ ...s, query: { error: `Search failed: ${err.message}` } }));
      toast(`Search failed: ${err.message}`, 'error', 6000);
    } finally {
      setLoading(s => ({ ...s, query: false }));
    }
  };

  const handleGpt = async () => {
    if (!gptPrompt.trim()) return;
    const question = gptPrompt.trim();
    setGptPrompt('');
    setResults(s => ({ ...s, gpt: null }));
    setLoading(s => ({ ...s, gpt: true }));
    try {
      let convId = activeConv;
      if (!convId && user && token) {
        const headers = { ...authHeaders(token), 'Content-Type': 'application/json' };
        const body = repoUrl ? { repo_url: repoUrl } : {};
        const newConv = await requestJson(`${API_BASE}/conversations/`, { method: 'POST', headers, body: JSON.stringify(body) });
        convId = newConv.id;
        setActiveConv(convId);
        setConvRefreshKey(k => k + 1);
      }
      const params = new URLSearchParams({
        prompt: question,
        top_k: String(Number(topK)),
        include_context: 'true',
      });
      if (convId) params.set('conversation_id', String(convId));
      const opts = { method: 'POST', headers: { ...authHeaders(token) } };
      const data = await requestJson(`${API_BASE}/gpt/query?${params.toString()}`, opts);
      setResults(s => ({ ...s, gpt: data }));
      if (convId) fetchConversation(convId);
      if (data.confidence === 'high') toast('Answer ready (high confidence)', 'success');
      else if (data.confidence === 'medium') toast('Answer ready (medium confidence)', 'info');
    } catch (err) {
      setResults(s => ({ ...s, gpt: { error: `GPT query failed: ${err.message}` } }));
      toast(`Query failed: ${err.message}`, 'error', 6000);
    } finally {
      setLoading(s => ({ ...s, gpt: false }));
    }
  };

  if (page === 'home') {
    return (
      <div className="app">
        <main className="home">
          <nav className="topbar">
            <span className="brand"><span className="brand-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 18 22 12 16 6"/>
                <polyline points="8 6 2 12 8 18"/>
                <circle cx="12" cy="12" r="2"/>
              </svg>
            </span>CodeSense</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AuthButton />
              <button className="ghost-btn" onClick={() => setPage('app')}>Launch</button>
            </div>
          </nav>
          <section className="hero">
            <div className="hero-text">
              <span className="pill">AI-Powered Intelligence</span>
              <h1>Master your codebase<br/>with superhuman speed.</h1>
              <p>Connect any repository to unlock deep semantic search, architectural mapping, and AI-driven Q&A grounded directly in your code.</p>
              <button className="primary-btn" onClick={() => setPage('app')}>
                Get Started
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              </button>
            </div>
            <div className="hero-visual">
              <div className="hero-graphic">
                <div className="hero-ring r1"/>
                <div className="hero-ring r2"/>
                <div className="hero-ring r3"/>
                <div className="hero-ring r4"/>
              </div>
            </div>
          </section>
          <section className="steps">
            {[
              { t: 'Connect', d: 'Securely sync your repository and let our AI build an intelligent neural index.' },
              { t: 'Deep Search', d: 'Discover code through semantic meaning and intent, instantly finding what matters.' },
              { t: 'Ask Codebase', d: 'Have conversational interactions with your codebase to solve complex architectural questions.' },
            ].map((s, i) => (
              <div className="step-card" key={s.t}>
                <span className="step-num">0{i + 1}</span>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </div>
            ))}
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="app-layout" style={tab === 'qa' ? { height: '100vh', minHeight: '100vh' } : undefined}>
        <aside className="sidebar">
          <span className="brand"><span className="brand-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 18 22 12 16 6"/>
                <polyline points="8 6 2 12 8 18"/>
                <circle cx="12" cy="12" r="2"/>
              </svg>
            </span>CodeSense</span>
          <nav className="side-nav">
            {[
              { k: 'ingest', l: 'Connect Repo' },
              { k: 'tree', l: 'Architecture' },
              { k: 'search', l: 'Deep Search' },
              { k: 'qa', l: 'Ask Codebase' },
            ].map(t => (
              <button
                key={t.k}
                className={`nav-item ${tab === t.k ? 'active' : ''}`}
                onClick={() => setTab(t.k)}
              >
                <NavIcon name={t.k} />
                <span>{t.l}</span>
              </button>
            ))}
          </nav>
          <ConversationsPanel key={convRefreshKey} activeConv={activeConv} onSelect={(id) => { setActiveConv(id); setTab('qa'); }} onNew={(id) => { setActiveConv(id); setTab('qa'); }} repoUrl={repoUrl} />
          <div className="sidebar-bottom">
            <div className="repo-info">
              <span className="repo-label">Repository</span>
              <span className="repo-val">{repoUrl ? repoUrl.replace('https://github.com/', '') : 'Not set'}</span>
            </div>
            <AuthButton />
            <button className="ghost-btn small" onClick={() => setPage('home')}>Home</button>
          </div>
        </aside>
        <main className="main-area">

          {tab === 'ingest' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Connect Repository</h2>
                <p>Sync your codebase to build a powerful neural vector index.</p>
              </div>
              <div className="feature-body">
                <div className="field">
                  <label>GitHub URL</label>
                  <input className="input" value={repoUrl} onChange={e => setRepoUrl(e.target.value)} placeholder="https://github.com/org/repo" />
                </div>
                <div className="field-row">
                  <div className="field">
                    <label>Max Files</label>
                    <input className="input" type="number" value={maxFiles} min="1" onChange={e => setMaxFiles(e.target.value)} />
                  </div>
                  <button className="primary-btn" onClick={handleIngest} disabled={loading.ingest || !isValidUrl}>
                    {loading.ingest ? 'Connecting...' : 'Connect'}
                  </button>
                </div>
                <IngestResult data={results.ingest} loading={loading.ingest} />
                {results.ingest && !results.ingest.error && (
                  <button className="ghost-btn small" onClick={async () => {
                    try {
                      await requestJson(`${API_BASE}/architecture/clear`, { method: 'POST' });
                      setResults(s => ({ ...s, ingest: null }));
                    } catch (e) {
                      setResults(s => ({ ...s, ingest: { error: e.message } }));
                    }
                  }} style={{ marginTop: 8 }}>
                    Reset neural index
                  </button>
                )}
              </div>
            </section>
          )}

          {tab === 'tree' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Codebase Architecture</h2>
                <p>Interactive visualization of modules, layers, and dependencies.</p>
              </div>
              <ArchitecturePanel />
            </section>
          )}

          {tab === 'search' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Deep Semantic Search</h2>
                <p>Locate code snippets instantly using AI-driven meaning.</p>
              </div>
              <div className="feature-body">
                <div className="field-row">
                  <div className="field" style={{ flex: 1 }}>
                    <label>Query</label>
                    <input className="input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by meaning..." />
                  </div>
                  <button className="primary-btn" onClick={handleSearch} disabled={loading.query}>
                    {loading.query ? 'Searching...' : 'Deep Search'}
                  </button>
                </div>
                <SearchResult data={results.query} loading={loading.query} />
              </div>
            </section>
          )}

          {tab === 'qa' && (
            <section className="feature-page fade-in qa-page">
              <div className="feature-header">
                <h2>Ask the Codebase</h2>
                <p>Get instant, grounded answers directly from your repository's code.</p>
                {!repoUrl && <div className="status-badge error" style={{ marginTop: 12 }}>No repository connected. Go to Connect Repo tab first.</div>}
              </div>
              {repoUrl && (
                  <div className="qa-layout" style={{ height: '100%' }}>
                  <div className="qa-top-bar">
                    {user ? (
                      activeConv && convData ? (
                        <span className="flow-step" style={{ cursor: 'pointer' }} onClick={() => { setActiveConv(null); setConvData(null); }}>
                          {convData.title} &times;
                        </span>
                      ) : (
                        <span className="conv-hint">Create a conversation in the sidebar to save Q&A history</span>
                      )
                    ) : (
                      <span className="conv-hint">Sign in to save conversation history</span>
                    )}
                  </div>
                  <div className="qa-messages">
                    {convData && convData.messages && convData.messages.length > 0 && (
                      <div className="chat-thread">
                        {convData.messages.map(m => (
                          <div key={m.id} className={`chat-message ${m.role}`}>
                            <div className="chat-role">{m.role === 'user' ? 'You' : 'Assistant'}</div>
                            <div className="chat-content">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {(results.gpt || loading.gpt) && <GptResult data={results.gpt} loading={loading.gpt} hideAnswer={!!(convData?.messages?.length)} />}
                    {!convData?.messages?.length && !loading.gpt && !results.gpt && (
                      <div className="qa-empty-spacer" />
                    )}
                  </div>
                  <div className="qa-input-area">
                    <div className="field-row" style={{ flex: 1 }}>
                      <div className="field" style={{ flex: 1, margin: 0 }}>
                        <input
                          className="input"
                          value={gptPrompt}
                          onChange={e => setGptPrompt(e.target.value)}
                          placeholder="Ask a question about this codebase..."
                        />
                      </div>
                      <button className="primary-btn" onClick={handleGpt} disabled={loading.gpt}>
                        {loading.gpt ? 'Generating...' : 'Ask AI'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </section>
          )}

        </main>
      </div>
    </div>
  );
}

function App() {
  return <AuthProvider><ToastProvider><AppInner /></ToastProvider></AuthProvider>;
}
export default App;
