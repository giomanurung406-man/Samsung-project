from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import nltk
from nltk.tokenize import sent_tokenize
import os
import uuid
from werkzeug.utils import secure_filename
import docx
import PyPDF2
import textract
import requests  # Untuk komunikasi dengan Ollama API
import logging 

app = Flask(__name__)
CORS(app)

# Konfigurasi upload file
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Konfigurasi Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"  # Ganti dengan model yang Anda inginkan
OLLAMA_ENABLED = True  # Set False untuk nonaktifkan Ollama

# Buat folder uploads jika belum ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Preprocessing teks sederhana
def preprocess_text(text):
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# Fungsi untuk memisahkan teks menjadi paragraf
def split_into_paragraphs(text):
    # Pisahkan teks menjadi paragraf berdasarkan baris baru
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    # Jika tidak ada paragraf yang terdeteksi, coba pisahkan dengan baris tunggal
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    
    return paragraphs

# Fungsi untuk membaca berbagai jenis file
def read_file(file_path, filename):
    if filename.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    elif filename.endswith('.docx'):
        doc = docx.Document(file_path)
        return '\n\n'.join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
    elif filename.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() + '\n\n'
            return text
    else:
        # Fallback menggunakan textract
        try:
            return textract.process(file_path).decode('utf-8', errors='ignore')
        except:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

# Fungsi untuk menganalisis teks dengan Ollama API
def analyze_with_ollama(text, source_text):
    if not OLLAMA_ENABLED:
        return {"analysis": "Ollama analysis disabled", "score": 0}
    
    try:
        # Siapkan prompt yang jelas untuk Ollama
        prompt = f"""
        ANALISIS KEMIRIPAN TEKS
        
        TUGAS: Analisislah kemiripan antara dua teks berikut dan berikan penilaian numerik (0-100) tentang tingkat kesamaan.
        
        TEKS 1 (Yang Dicek):
        {text}
        
        TEKS 2 (Sumber):
        {source_text}
        
        FORMAT OUTPUT:
        - Berikan hanya angka antara 0-100 yang merepresentasikan persentase kemiripan
        - Setelah angka, berikan analisis singkat 1-2 kalimat
        
        CONTOH OUTPUT:
        75
        Teks menunjukkan kemiripan struktur dan ide utama tetapi menggunakan kosakata yang berbeda dalam beberapa bagian.
        """
        
        # Kirim request ke Ollama API
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
        )
        
        
        print(response, flush=True)
            
        if response.status_code != 200:
            return {
                "analysis": f"Error: Ollama API returned status {response.status_code}",
                "score": 0
            }
        
        result = response.json()
        response_text = result.get('response', '')
        
        # Ekstrak skor numerik dari respons
        score_match = re.search(r'(\d{1,3})', response_text)
        if score_match:
            score = int(score_match.group(1))
            # Pastikan score antara 0-100
            score = max(0, min(100, score))
        else:
            score = 0
        
        # Ekstrak analisis (ambil teks setelah angka)
        analysis = response_text.replace(str(score), '').strip()
        if not analysis or analysis == "":
            analysis = "Tidak ada analisis yang dihasilkan oleh model."
        
        return {
            "analysis": analysis,
            "score": score / 100  # Convert ke decimal
        }
    except Exception as e:
        print(f"Error in Ollama analysis: {e}")
        return {
            "analysis": f"Error dalam analisis: {str(e)}",
            "score": 0
        }

# Fungsi untuk memeriksa plagiarisme dalam dokumen
def check_document_plagiarism(text, sources):
    # Pisahkan teks menjadi paragraf
    paragraphs = split_into_paragraphs(text)
    results = []
    
    # Untuk setiap paragraf, periksa similarity dengan semua sumber
    for i, paragraph in enumerate(paragraphs):
        if len(paragraph.split()) < 5:  # Abaikan paragraf terlalu pendek
            continue
            
        paragraph_results = []
        for source_name, source_text in sources.items():
            # Pisahkan sumber menjadi paragraf juga
            source_paragraphs = split_into_paragraphs(source_text)
            
            # Untuk setiap paragraf dalam sumber, hitung similarity dengan Ollama
            for j, source_paragraph in enumerate(source_paragraphs):
                if len(source_paragraph.split()) < 5:  # Abaikan paragraf terlalu pendek
                    continue
                    
                # Analisis dengan Ollama untuk setiap pasangan paragraf
                ollama_analysis = analyze_with_ollama(paragraph, source_paragraph)
                similarity = ollama_analysis['score']
                
                if similarity > 0.3:  # Hanya tampilkan jika similarity > 30%
                    paragraph_results.append({
                        'source_name': source_name,
                        'source_paragraph': j + 1,
                        'similarity': round(similarity * 100, 2),
                        'matched_text': source_paragraph[:200] + "..." if len(source_paragraph) > 200 else source_paragraph,
                        'ai_analysis': ollama_analysis['analysis'],
                    })
        
        # Urutkan hasil berdasarkan similarity tertinggi
        paragraph_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        if paragraph_results:
            results.append({
                'paragraph_number': i + 1,
                'paragraph_text': paragraph[:300] + "..." if len(paragraph) > 300 else paragraph,
                'matches': paragraph_results
            })
    
    return results

# API endpoint untuk deteksi plagiarisme
@app.route('/api/check-plagiarism', methods=['POST'])
def check_plagiarism():
    try:
        data = request.get_json()
        text = data.get('text', '')
        sources = data.get('sources', {})
        
        if not text:
            return jsonify({'error': 'Teks harus diisi'}), 00
        
        # Periksa plagiarisme
        results = check_document_plagiarism(text, sources)
        
        # Hitung overall similarity score
        total_similarity = 0
        total_paragraphs = len(results)
        
        for result in results:
            if result['matches']:
                total_similarity += result['matches'][0]['similarity']
        
        overall_score = round(total_similarity / total_paragraphs, 2) if total_paragraphs > 0 else 0
        
        # Tentukan status plagiarisme
        if overall_score >= 70:
            status = "Tinggi (Kemungkinan Plagiarisme Tinggi)"
        elif overall_score >= 40:
            status = "Sedang (Perlu Pemeriksaan Lebih Lanjut)"
        else:
            status = "Rendah (Kemungkinan Original)"
        
        response = {
            'overall_score': overall_score,
            'status': status,
            'total_paragraphs': total_paragraphs,
            'results': results,
            'ollama_enabled': OLLAMA_ENABLED,
            'details': f"Tingkat kesamaan keseluruhan adalah {overall_score}% dari {total_paragraphs} paragraf yang dianalisis"
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint untuk upload file
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Tidak ada file yang diunggah'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nama file kosong'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_id = str(uuid.uuid4())
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
            file.save(file_path)
            
            # Baca isi file
            content = read_file(file_path, filename)
            
            # Hapus file setelah dibaca
            os.remove(file_path)
            
            return jsonify({
                'success': True,
                'content': content,
                'filename': filename
            })
        
        return jsonify({'error': 'Tipe file tidak diizinkan'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint untuk mendapatkan model Ollama yang tersedia
@app.route('/api/ollama-models', methods=['GET'])
def get_ollama_models():
    try:
        if not OLLAMA_ENABLED:
            return jsonify({'error': 'Ollama tidak diaktifkan'}), 400
            
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags")
        if response.status_code != 200:
            return jsonify({'error': f'Ollama API error: {response.status_code}'}), 500
            
        data = response.json()
        return jsonify({'models': data.get('models', [])})
    except Exception as e:
        return jsonify({'error': f'Gagal mengambil model Ollama: {str(e)}'}), 500

# API endpoint untuk mengubah model Ollama
@app.route('/api/change-model', methods=['POST'])
def change_ollama_model():
    try:
        if not OLLAMA_ENABLED:
            return jsonify({'error': 'Ollama tidak diaktifkan'}), 400
            
        data = request.get_json()
        model_name = data.get('model_name')
        
        if not model_name:
            return jsonify({'error': 'Nama model harus disediakan'}), 400
            
        # Cek apakah model tersedia
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags")
        if response.status_code != 200:
            return jsonify({'error': f'Ollama API error: {response.status_code}'}), 500
            
        data = response.json()
        available_models = [m['name'] for m in data.get('models', [])]
        
        if model_name not in available_models:
            return jsonify({'error': f'Model {model_name} tidak tersedia'}), 400
            
        global OLLAMA_MODEL
        OLLAMA_MODEL = model_name
        
        return jsonify({'success': True, 'message': f'Model diubah menjadi {model_name}'})
    except Exception as e:
        return jsonify({'error': f'Gagal mengubah model: {str(e)}'}), 500

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    # Download NLTK data jika belum ada
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    
    app.run(debug=True, port=5000)
