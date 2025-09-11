from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
import string
import os
import uuid
from werkzeug.utils import secure_filename
import docx
import PyPDF2
import textract
import io
import ollama  # Import library Ollama

app = Flask(__name__)
CORS(app)  # Mengizinkan request dari frontend React

# Konfigurasi upload file
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Konfigurasi Ollama
OLLAMA_MODEL = "llama3"  # Ganti dengan model yang Anda inginkan
OLLAMA_ENABLED = True  # Set False untuk nonaktifkan Ollama

# Buat folder uploads jika belum ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Preprocessing teks
def preprocess_text(text):
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Tokenize
    tokens = word_tokenize(text)
    # Remove stopwords
    stop_words = set(stopwords.words('indonesian') + stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    # Join tokens back to text
    processed_text = ' '.join(filtered_tokens)
    return processed_text

# Fungsi untuk memisahkan teks menjadi paragraf
def split_into_paragraphs(text, min_sentences=1):
    # Pisahkan teks menjadi paragraf berdasarkan baris baru
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    # Jika tidak ada paragraf yang terdeteksi, coba pisahkan dengan baris tunggal
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    
    # Gabungkan paragraf yang terlalu pendek
    merged_paragraphs = []
    current_paragraph = ""
    
    for paragraph in paragraphs:
        sentences = sent_tokenize(paragraph)
        if len(sentences) < min_sentences and current_paragraph:
            current_paragraph += " " + paragraph
        else:
            if current_paragraph:
                merged_paragraphs.append(current_paragraph)
            current_paragraph = paragraph
    
    if current_paragraph:
        merged_paragraphs.append(current_paragraph)
    
    return merged_paragraphs

# Fungsi untuk membaca berbagai jenis file
def read_file(file_path, filename):
    if filename.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
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
        return textract.process(file_path).decode('utf-8')

# Fungsi untuk menghitung similarity antara dua teks
def calculate_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    
    # Preprocess kedua teks
    processed_text1 = preprocess_text(text1)
    processed_text2 = preprocess_text(text2)
    
    # Buat TF-IDF Vectorizer
    vectorizer = TfidfVectorizer()
    
    # Transform teks menjadi vektor TF-IDF
    try:
        tfidf_matrix = vectorizer.fit_transform([processed_text1, processed_text2])
        # Hitung cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity[0][0]
    except:
        return 0.0

# Fungsi untuk menganalisis teks dengan Ollama
def analyze_with_ollama(text, source_text):
    if not OLLAMA_ENABLED:
        return {"analysis": "Ollama analysis disabled", "score": 0}
    
    try:
        prompt = f"""
        Saya ingin Anda menganalisis kemiripan antara dua teks berikut dan memberikan penilaian tentang kemungkinan plagiarisme.
        
        TEKS YANG DICEK:
        {text}
        
        TEKS SUMBER:
        {source_text}
        
        Berikan analisis dengan format:
        - Tingkat Kesamaan: (persentase)
        - Analisis: (penjelasan singkat tentang kemiripan)
        - Rekomendasi: (saran jika ditemukan plagiarisme)
        """
        
        response = ollama.chat(model=OLLAMA_MODEL, messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ])
        
        analysis_result = response['message']['content']
        
        # Ekstrak skor dari respons
        score_match = re.search(r'Tingkat Kesamaan:\s*(\d+)%', analysis_result)
        score = int(score_match.group(1)) / 100 if score_match else 0
        
        return {
            "analysis": analysis_result,
            "score": score
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
        if len(word_tokenize(paragraph)) < 10:  # Abaikan paragraf terlalu pendek
            continue
            
        paragraph_results = []
        for source_name, source_text in sources.items():
            # Pisahkan sumber menjadi paragraf juga
            source_paragraphs = split_into_paragraphs(source_text)
            
            # Untuk setiap paragraf dalam sumber, hitung similarity
            for j, source_paragraph in enumerate(source_paragraphs):
                if len(word_tokenize(source_paragraph)) < 10:  # Abaikan paragraf terlalu pendek
                    continue
                    
                similarity = calculate_similarity(paragraph, source_paragraph)
                if similarity > 0.3:  # Hanya tampilkan jika similarity > 30%
                    # Analisis dengan Ollama untuk paragraf dengan similarity tinggi
                    ollama_analysis = analyze_with_ollama(paragraph, source_paragraph)
                    
                    paragraph_results.append({
                        'source_name': source_name,
                        'source_paragraph': j + 1,
                        'similarity': round(similarity * 100, 2),
                        'matched_text': source_paragraph[:200] + "..." if len(source_paragraph) > 200 else source_paragraph,
                        'ai_analysis': ollama_analysis['analysis'],
                        'ai_score': ollama_analysis['score'] * 100
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
            return jsonify({'error': 'Teks harus diisi'}), 400
        
        # Periksa plagiarisme
        results = check_document_plagiarism(text, sources)
        
        # Hitung overall similarity score
        total_similarity = 0
        total_ai_similarity = 0
        total_paragraphs = len(results)
        
        for result in results:
            if result['matches']:
                total_similarity += result['matches'][0]['similarity']
                total_ai_similarity += result['matches'][0].get('ai_score', 0)
        
        overall_score = round(total_similarity / total_paragraphs, 2) if total_paragraphs > 0 else 0
        overall_ai_score = round(total_ai_similarity / total_paragraphs, 2) if total_paragraphs > 0 else 0
        
        # Tentukan status plagiarisme
        if overall_score >= 70 or overall_ai_score >= 70:
            status = "Tinggi (Kemungkinan Plagiarisme Tinggi)"
        elif overall_score >= 40 or overall_ai_score >= 40:
            status = "Sedang (Perlu Pemeriksaan Lebih Lanjut)"
        else:
            status = "Rendah (Kemungkinan Original)"
        
        response = {
            'overall_score': overall_score,
            'overall_ai_score': overall_ai_score,
            'status': status,
            'total_paragraphs': total_paragraphs,
            'results': results,
            'ollama_enabled': OLLAMA_ENABLED,
            'details': f"Tingkat kesamaan keseluruhan adalah {overall_score}% (AI: {overall_ai_score}%) dari {total_paragraphs} paragraf yang dianalisis"
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
            
        models = ollama.list()
        return jsonify({'models': models.get('models', [])})
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
        models = ollama.list()
        available_models = [m['name'] for m in models.get('models', [])]
        
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
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')
    
    app.run(debug=True, port=5000)