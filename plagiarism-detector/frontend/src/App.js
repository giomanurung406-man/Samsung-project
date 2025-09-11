import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [text, setText] = useState('');
  const [sources, setSources] = useState({});
  const [sourceName, setSourceName] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('input');

  const handleAddSource = () => {
    if (!sourceName.trim() || !sourceText.trim()) {
      setError('Nama sumber dan teks sumber harus diisi!');
      return;
    }

    const newSources = { ...sources, [sourceName]: sourceText };
    setSources(newSources);
    setSourceName('');
    setSourceText('');
    setError('');
  };

  const handleRemoveSource = (name) => {
    const newSources = { ...sources };
    delete newSources[name];
    setSources(newSources);
  };

  const handleCheckPlagiarism = async () => {
    if (!text.trim()) {
      setError('Teks utama harus diisi!');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post('http://127.0.0.1:5000/api/check-plagiarism', {
        text,
        sources
      });
      
      setResult(response.data);
      setActiveTab('results');
    } catch (err) {
      setError('Terjadi kesalahan. Pastikan backend server berjalan di port 5000.');
      console.error(err);
    }
    
    setLoading(false);
  };

  const handleClear = () => {
    setText('');
    setSources({});
    setResult(null);
    setError('');
    setActiveTab('input');
  };

  const handleFileUpload = async (event, isSource = false) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:5000/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      if (isSource) {
        setSourceText(response.data.content);
        if (!sourceName) {
          setSourceName(file.name);
        }
      } else {
        setText(response.data.content);
      }
    } catch (err) {
      setError('Gagal mengunggah file.');
      console.error(err);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Detektor Plagiarisme Multi-Paragraf</h1>
        <p>Analisis teks untuk mendeteksi plagiarisme dari berbagai sumber</p>
      </header>

      <div className="container">
        {error && <div className="error">{error}</div>}
        
        <div className="tabs">
          <button 
            className={activeTab === 'input' ? 'active' : ''}
            onClick={() => setActiveTab('input')}
          >
            Input Teks
          </button>
          <button 
            className={activeTab === 'sources' ? 'active' : ''}
            onClick={() => setActiveTab('sources')}
          >
            Sumber Referensi
          </button>
          <button 
            className={activeTab === 'results' ? 'active' : ''}
            onClick={() => setActiveTab('results')}
            disabled={!result}
          >
            Hasil
          </button>
        </div>

        {activeTab === 'input' && (
          <div className="tab-content">
            <div className="text-input">
              <h3>Teks yang akan Diperiksa</h3>
              <div className="file-upload">
                <label>
                  Unggah File (TXT, DOCX, PDF)
                  <input 
                    type="file" 
                    accept=".txt,.docx,.pdf"
                    onChange={(e) => handleFileUpload(e, false)}
                  />
                </label>
              </div>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Masukkan teks yang akan diperiksa di sini..."
                rows="15"
              />
            </div>
          </div>
        )}

        {activeTab === 'sources' && (
          <div className="tab-content">
            <h3>Sumber Referensi</h3>
            <div className="source-input">
              <div className="file-upload">
                <label>
                  Unggah File Sumber (TXT, DOCX, PDF)
                  <input 
                    type="file" 
                    accept=".txt,.docx,.pdf"
                    onChange={(e) => handleFileUpload(e, true)}
                  />
                </label>
              </div>
              <input
                type="text"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                placeholder="Nama sumber (contoh: Wikipedia, Buku A, dll)"
                className="source-name"
              />
              <textarea
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Masukkan teks sumber referensi di sini..."
                rows="10"
              />
              <button onClick={handleAddSource} className="add-source-btn">
                Tambahkan Sumber
              </button>
            </div>

            <div className="sources-list">
              <h4>Sumber yang Ditambahkan ({Object.keys(sources).length})</h4>
              {Object.keys(sources).length === 0 ? (
                <p>Belum ada sumber yang ditambahkan</p>
              ) : (
                <ul>
                  {Object.entries(sources).map(([name, content]) => (
                    <li key={name}>
                      <span>{name}</span>
                      <button onClick={() => handleRemoveSource(name)}>Hapus</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {activeTab === 'results' && result && (
          <div className="tab-content">
            <h2>Hasil Deteksi Plagiarisme</h2>
            <div className="overall-result">
              <div className={`score ${result.overall_score > 70 ? 'high' : result.overall_score > 40 ? 'medium' : 'low'}`}>
                Tingkat Kesamaan Keseluruhan: {result.overall_score}%
              </div>
              <div className="status">Status: {result.status}</div>
              <p>{result.details}</p>
            </div>

            <div className="detailed-results">
              <h3>Detail Per Paragraf</h3>
              {result.results.length === 0 ? (
                <p>Tidak ditemukan indikasi plagiarisme</p>
              ) : (
                result.results.map((paragraph, idx) => (
                  <div key={idx} className="paragraph-result">
                    <h4>Paragraf #{paragraph.paragraph_number}</h4>
                    <p className="paragraph-text">{paragraph.paragraph_text}</p>
                    
                    <div className="matches">
                      <h5>Kecocokan ditemukan:</h5>
                      {paragraph.matches.map((match, matchIdx) => (
                        <div key={matchIdx} className="match">
                          <div className="match-source">
                            <strong>Sumber:</strong> {match.source_name} (Paragraf #{match.source_paragraph})
                          </div>
                          <div className="match-similarity">
                            <strong>Tingkat Kesamaan:</strong> {match.similarity}%
                          </div>
                          <div className="match-text">
                            <strong>Teks yang Cocok:</strong> {match.matched_text}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="actions">
          <button 
            onClick={handleCheckPlagiarism} 
            disabled={loading || !text.trim()}
            className="check-btn"
          >
            {loading ? 'Memeriksa...' : 'Periksa Plagiarisme'}
          </button>
          
          <button onClick={handleClear} className="clear-btn">
            Bersihkan Semua
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;