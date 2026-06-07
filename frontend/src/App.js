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

function FieldHint({ children }) {
  return <p className="field-hint">{children}</p>;
}

function EmptyState({ text }) {
  return <div className="empty-state">{text}</div>;
}

function ErrorState({ text }) {
  return <div className="error-state">{text}</div>;
}

function IngestResult({ data }) {
  if (!data) return <EmptyState text="No ingestion result yet." />;
  if (data.error) return <ErrorState text={data.error} />;

  return (
    <div className="result-panel">
      <div className="result-row"><span>Repository</span><strong>{data.repo || '-'}</strong></div>
      <div className="result-row"><span>Files Ingested</span><strong>{data.files_ingested ?? 0}</strong></div>
      <div className="result-row"><span>Chunks Created</span><strong>{data.chunks_ingested ?? 0}</strong></div>
      <div className="result-row"><span>Sample File</span><strong>{data.sample_file || '-'}</strong></div>
    </div>
  );
}

function SearchResult({ data }) {
  if (!data) return <EmptyState text="Run a vector search to see semantic matches." />;
  if (data.error) return <ErrorState text={data.error} />;

  if (!Array.isArray(data.results) || data.results.length === 0) {
    return <EmptyState text="No similar chunks found for this query." />;
  }

  return (
    <div className="result-list">
      {data.results.map((item) => (
        <article className="result-item" key={`${item.rank}-${item.metadata?.chunk_id || item.score}`}>
          <div className="result-item-top">
            <span className="result-rank">Rank {item.rank}</span>
            <span className="result-score">score {Number(item.score).toFixed(3)}</span>
          </div>
          <p className="result-path">{item.metadata?.path || 'unknown'}</p>
          <pre className="result-chunk">{item.chunk}</pre>
        </article>
      ))}
    </div>
  );
}

function LlamaResult({ data }) {
  if (!data) return <EmptyState text="Ask a question to get a grounded answer." />;
  if (data.error) return <ErrorState text={data.error} />;

  return (
    <div className="result-panel">
      <div className="result-answer-block">
        <h4>Answer</h4>
        <pre className="result-answer">{data.result || 'NOT FOUND IN CONTEXT'}</pre>
      </div>
      {Array.isArray(data.context) && data.context.length > 0 && (
        <div className="result-context-block">
          <h4>Context ({data.context.length})</h4>
          <div className="result-list">
            {data.context.map((ctx, i) => (
              <article className="result-item" key={`${ctx.metadata?.chunk_id || i}`}>
                <p className="result-path">{ctx.metadata?.path || ctx.source || 'unknown'}</p>
                <pre className="result-chunk">{ctx.chunk}</pre>
              </article>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [message, setMessage] = useState('');
  const [step, setStep] = useState('intro');

  const [maxFiles, setMaxFiles] = useState(500);
  const [query, setQuery] = useState('');
  const [llamaPrompt, setLlamaPrompt] = useState('');
  const [topK, setTopK] = useState(3);

  const [loading, setLoading] = useState({ ingest: false, query: false, llama: false });
  const [results, setResults] = useState({ ingest: null, query: null, llama: null });

  const canContinue = useMemo(() => websiteUrl.trim().length > 0, [websiteUrl]);

  const handleSubmit = (e) => {
    e.preventDefault();

    const value = websiteUrl.trim();
    if (!value) {
      setMessage('Please enter a project link.');
      return;
    }

    try {
      // eslint-disable-next-line no-new
      new URL(value);
      setMessage('Project link saved. Continue to workspace to ingest and query.');
    } catch {
      setMessage('Please enter a valid URL. Example: https://github.com/org/repo');
    }
  };

  const handleIngest = async () => {
    if (!websiteUrl.trim()) {
      setResults((s) => ({ ...s, ingest: { error: 'Please save a repository URL first.' } }));
      return;
    }

    setLoading((s) => ({ ...s, ingest: true }));
    try {
      const data = await requestJson(`${API_BASE}/github/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: websiteUrl.trim(), max_files: Number(maxFiles) }),
      });
      setResults((s) => ({ ...s, ingest: data }));
    } catch (err) {
      setResults((s) => ({ ...s, ingest: { error: `Ingest failed: ${err.message}` } }));
    } finally {
      setLoading((s) => ({ ...s, ingest: false }));
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      setResults((s) => ({ ...s, query: { error: 'Please enter a search query.' } }));
      return;
    }

    setLoading((s) => ({ ...s, query: true }));
    try {
      const data = await requestJson(`${API_BASE}/query/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), top_k: Number(topK) }),
      });
      setResults((s) => ({ ...s, query: data }));
    } catch (err) {
      setResults((s) => ({ ...s, query: { error: `Search failed: ${err.message}` } }));
    } finally {
      setLoading((s) => ({ ...s, query: false }));
    }
  };

  const handleLlama = async () => {
    if (!llamaPrompt.trim()) {
      setResults((s) => ({ ...s, llama: { error: 'Please enter a prompt.' } }));
      return;
    }

    setLoading((s) => ({ ...s, llama: true }));
    try {
      const params = new URLSearchParams({
        prompt: llamaPrompt.trim(),
        top_k: String(Number(topK)),
        include_context: 'true',
      });
      const data = await requestJson(`${API_BASE}/llama/query?${params.toString()}`, { method: 'POST' });
      setResults((s) => ({ ...s, llama: data }));
    } catch (err) {
      setResults((s) => ({ ...s, llama: { error: `LLaMA query failed: ${err.message}` } }));
    } finally {
      setLoading((s) => ({ ...s, llama: false }));
    }
  };

  return (
    <div className="App">
      <header className="hero">
        <h1>Code-App RAG</h1>
        <p>Analyze repositories with retrieval-augmented generation, search code semantically, and run grounded Q and A.</p>
      </header>

      {step === 'intro' && (
        <main className="intro-card">
          <h2>Get Started</h2>
          <p className="intro-text">Paste your project repository link to start an ingestion and analysis workflow.</p>

          <form onSubmit={handleSubmit} className="link-form">
            <label htmlFor="websiteUrl">Repository Link</label>
            <input
              id="websiteUrl"
              type="url"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://github.com/your-org/your-project"
            />
            <button type="submit">Save Link</button>
          </form>

          {message && <p className="form-message">{message}</p>}

          <div className="intro-actions">
            <button type="button" onClick={() => setStep('workspace')} disabled={!canContinue}>
              Continue to Workspace
            </button>
          </div>
        </main>
      )}

      {step === 'workspace' && (
        <main className="workspace">
          <div className="workspace-topbar">
            <div>
              <p className="topbar-label">Current Project</p>
              <p className="topbar-link">{websiteUrl || 'Not set'}</p>
            </div>
            <button type="button" onClick={() => setStep('intro')}>Back</button>
          </div>

          <section className="workspace-grid">
            <article className="card">
              <h3>Ingest Repository</h3>
              <FieldHint>Fetch repository files and build vector chunks for retrieval.</FieldHint>
              <label htmlFor="maxFiles">Max Files</label>
              <input id="maxFiles" type="number" value={maxFiles} min="1" onChange={(e) => setMaxFiles(e.target.value)} />
              <button type="button" onClick={handleIngest} disabled={loading.ingest || !websiteUrl.trim()}>
                {loading.ingest ? 'Ingesting...' : 'Ingest'}
              </button>
              <IngestResult data={results.ingest} />
            </article>

            <article className="card">
              <h3>Vector Search</h3>
              <FieldHint>Search top semantic chunks from the indexed repository.</FieldHint>
              <label htmlFor="query">Search Query</label>
              <input id="query" type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="order, anomaly, payment" />
              <label htmlFor="topK">Top K</label>
              <input id="topK" type="number" value={topK} min="1" onChange={(e) => setTopK(e.target.value)} />
              <button type="button" onClick={handleSearch} disabled={loading.query}>
                {loading.query ? 'Searching...' : 'Search'}
              </button>
              <SearchResult data={results.query} />
            </article>

            <article className="card">
              <h3>LLaMA Q and A</h3>
              <FieldHint>Ask a grounded question using retrieved context chunks.</FieldHint>
              <label htmlFor="llamaPrompt">Prompt</label>
              <input
                id="llamaPrompt"
                type="text"
                value={llamaPrompt}
                onChange={(e) => setLlamaPrompt(e.target.value)}
                placeholder="Which method is used to detect anomaly?"
              />
              <button type="button" onClick={handleLlama} disabled={loading.llama}>
                {loading.llama ? 'Asking...' : 'Ask LLaMA'}
              </button>
              <LlamaResult data={results.llama} />
            </article>
          </section>
        </main>
      )}
    </div>
  );
}

export default App;
