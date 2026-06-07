import React, { useMemo, useState } from 'react';
import './App.css';

const API_BASE = 'http://127.0.0.1:8000';

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

const NavIcon = ({ name }) => {
  const paths = {
    ingest: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
    search: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
    qa: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
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
            <span className="brand">CodeApp</span>
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
              <div className="code-window">
                <div className="win-dots"><span/><span/><span/></div>
                <div className="win-body">
                  <div className="win-line w90"/><div className="win-line w70"/><div className="win-line w85"/><div className="win-line w50"/>
                  <div className="win-line w90 blink"/><div className="win-line w75"/><div className="win-line w60"/>
                </div>
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
          <span className="brand">CodeApp</span>
          <nav className="side-nav">
            {[
              { k: 'ingest', l: 'Ingest' },
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
            <section className="feature-page">
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
              </div>
            </section>
          )}

          {tab === 'search' && (
            <section className="feature-page">
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
            <section className="feature-page">
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
