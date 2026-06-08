import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

const API_BASE = window.location.origin === 'http://localhost:3000' ? 'http://127.0.0.1:8000' : '';

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

function IngestResult({ data }) {
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

function SearchResult({ data }) {
  if (!data) return <p className="hint">Run a search to see results</p>;
  if (data.error) return <div className="status-badge error">{data.error}</div>;
  if (!Array.isArray(data.results) || data.results.length === 0)
    return <p className="hint">No similar chunks found</p>;
  return (
    <div className="result-list">
      {data.results.map((item) => (
        <div className="chunk-card" key={`${item.rank}-${item.metadata?.chunk_id || item.score}`}>
          <div className="chunk-meta">
            <span className="chunk-rank">#{item.rank}</span>
            <span className="chunk-score">{Number(item.score).toFixed(3)}</span>
          </div>
          <p className="chunk-path">{item.metadata?.path || 'unknown'}</p>
          <pre className="chunk-code">{item.chunk}</pre>
        </div>
      ))}
    </div>
  );
}

function LlamaResult({ data }) {
  if (!data) return <p className="hint">Ask a question to get an answer</p>;
  if (data.error) return <div className="status-badge error">{data.error}</div>;
  const isLow = data.confidence === 'low';
  return (
    <div className="qa-result">
      <div className={`answer-box ${isLow ? 'low' : ''}`}>
        <div className="answer-top">
          <span className="answer-lbl">Answer</span>
          {data.confidence && (
            <span className={`conf-badge ${data.confidence}`}>
              {data.confidence} &middot; {(data.confidence_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <pre className="answer-text">{data.result || 'No answer'}</pre>
      </div>
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
    } catch (err) {
      setError(err.message);
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

function App() {
  const [page, setPage] = useState('home');
  const [tab, setTab] = useState('ingest');
  const [repoUrl, setRepoUrl] = useState('');
  const [maxFiles, setMaxFiles] = useState(500);
  const [query, setQuery] = useState('');
  const [llamaPrompt, setLlamaPrompt] = useState('');
  const [topK, setTopK] = useState(3);
  const [loading, setLoading] = useState({ ingest: false, query: false, llama: false });
  const [results, setResults] = useState({ ingest: null, query: null, llama: null });

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
    } catch (err) {
      setResults(s => ({ ...s, ingest: { error: `Ingest failed: ${err.message}` } }));
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
    } catch (err) {
      setResults(s => ({ ...s, query: { error: `Search failed: ${err.message}` } }));
    } finally {
      setLoading(s => ({ ...s, query: false }));
    }
  };

  const handleLlama = async () => {
    if (!llamaPrompt.trim()) return;
    setLoading(s => ({ ...s, llama: true }));
    try {
      const params = new URLSearchParams({
        prompt: llamaPrompt.trim(),
        top_k: String(Number(topK)),
        include_context: 'true',
      });
      const data = await requestJson(`${API_BASE}/llama/query?${params.toString()}`, { method: 'POST' });
      setResults(s => ({ ...s, llama: data }));
    } catch (err) {
      setResults(s => ({ ...s, llama: { error: `LLaMA query failed: ${err.message}` } }));
    } finally {
      setLoading(s => ({ ...s, llama: false }));
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
            <button className="ghost-btn" onClick={() => setPage('app')}>Launch</button>
          </nav>
          <section className="hero">
            <div className="hero-text">
              <span className="pill">RAG-powered Code Analysis</span>
              <h1>Understand any codebase<br/>through retrieval.</h1>
              <p>Ingest, search, and query GitHub repositories with retrieval-augmented generation grounded in your actual code.</p>
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
              { t: 'Ingest', d: 'Pull code from any GitHub repository and chunk it intelligently for search.' },
              { t: 'Search', d: 'Find relevant code by semantic meaning, not just keyword matching.' },
              { t: 'Query', d: 'Ask grounded questions answered directly from your codebase via LLM.' },
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
      <div className="app-layout">
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
              { k: 'ingest', l: 'Ingest' },
              { k: 'tree', l: 'Modules' },
              { k: 'search', l: 'Search' },
              { k: 'qa', l: 'Q&A' },
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
          <div className="sidebar-bottom">
            <div className="repo-info">
              <span className="repo-label">Repository</span>
              <span className="repo-val">{repoUrl ? repoUrl.replace('https://github.com/', '') : 'Not set'}</span>
            </div>
            <button className="ghost-btn small" onClick={() => setPage('home')}>Home</button>
          </div>
        </aside>
        <main className="main-area">

          {tab === 'ingest' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Ingest Repository</h2>
                <p>Fetch repository files and build searchable vector chunks.</p>
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
                    {loading.ingest ? 'Ingesting...' : 'Ingest'}
                  </button>
                </div>
                <IngestResult data={results.ingest} />
                {results.ingest && !results.ingest.error && (
                  <button className="ghost-btn small" onClick={async () => {
                    try {
                      await requestJson(`${API_BASE}/architecture/clear`, { method: 'POST' });
                      setResults(s => ({ ...s, ingest: null }));
                    } catch (e) {
                      setResults(s => ({ ...s, ingest: { error: e.message } }));
                    }
                  }} style={{ marginTop: 8 }}>
                    Reset vectorstore
                  </button>
                )}
              </div>
            </section>
          )}

          {tab === 'tree' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Module Graph</h2>
                <p>Visualize codebase modules, layers, and dependencies.</p>
              </div>
              <ArchitecturePanel />
            </section>
          )}

          {tab === 'search' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Semantic Search</h2>
                <p>Find code by meaning, not just keywords.</p>
              </div>
              <div className="feature-body">
                <div className="field-row">
                  <div className="field" style={{ flex: 1 }}>
                    <label>Query</label>
                    <input className="input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by meaning..." />
                  </div>
                  <button className="primary-btn" onClick={handleSearch} disabled={loading.query}>
                    {loading.query ? 'Searching...' : 'Search'}
                  </button>
                </div>
                <SearchResult data={results.query} />
              </div>
            </section>
          )}

          {tab === 'qa' && (
            <section className="feature-page fade-in">
              <div className="feature-header">
                <h2>Grounded Q&A</h2>
                <p>Ask questions answered from your actual codebase.</p>
              </div>
              <div className="feature-body">
                <div className="field">
                  <label>Question</label>
                  <input
                    className="input"
                    value={llamaPrompt}
                    onChange={e => setLlamaPrompt(e.target.value)}
                    placeholder="What does this project do?"
                  />
                </div>
                <button className="primary-btn" onClick={handleLlama} disabled={loading.llama}>
                  {loading.llama ? 'Generating...' : 'Ask'}
                </button>
                <LlamaResult data={results.llama} />
              </div>
            </section>
          )}

        </main>
      </div>
    </div>
  );
}

export default App;
