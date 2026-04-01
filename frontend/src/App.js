import React, { useState } from 'react';
import './App.css';
import GitHubIngest from './components/GitHubIngest';
import QueryComponent from './components/QueryComponent';

function App() {
  const [activeTab, setActiveTab] = useState('ingest');
  const [ingestStatus, setIngestStatus] = useState(null);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 Code RAG System</h1>
        <p>GitHub Ingestion & Code Query</p>
      </header>

      <div className="tabs">
        <button
          className={`tab-btn ${activeTab === 'ingest' ? 'active' : ''}`}
          onClick={() => setActiveTab('ingest')}
        >
          📥 Ingest GitHub Repo
        </button>
        <button
          className={`tab-btn ${activeTab === 'query' ? 'active' : ''}`}
          onClick={() => setActiveTab('query')}
        >
          🔍 Query Code
        </button>
      </div>

      <div className="content">
        {activeTab === 'ingest' && (
          <GitHubIngest setIngestStatus={setIngestStatus} ingestStatus={ingestStatus} />
        )}
        {activeTab === 'query' && <QueryComponent />}
      </div>
    </div>
  );
}

export default App;
