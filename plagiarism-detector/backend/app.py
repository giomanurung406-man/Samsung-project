from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string

app = Flask(__name__)
CORS(app)  # Mengizinkan request dari frontend React

# Preprocessing teks
def preprocess_text(text):
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Tokenize
    tokens = word_tokenize(text)
    # Remove stopwords
    stop_words = set(stopwords.words('indonesian') + stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word not in stop_words]
    # Join tokens back to text
    processed_text = ' '.join(filtered_tokens)
    return processed_text

# Fungsi untuk menghitung similarity
def calculate_similarity(text1, text2):
    # Preprocess kedua teks
    processed_text1 = preprocess_text(text1)
    processed_text2 = preprocess_text(text2)
    
    # Buat TF-IDF Vectorizer
    vectorizer = TfidfVectorizer()
    
    # Transform teks menjadi vektor TF-IDF
    tfidf_matrix = vectorizer.fit_transform([processed_text1, processed_text2])
    
    # Hitung cosine similarity
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    
    return similarity[0][0]

# API endpoint untuk deteksi plagiarisme
@app.route('/api/check-plagiarism', methods=['POST'])
def check_plagiarism():
    try:
        data = request.get_json()
        text1 = data.get('text1', '')
        text2 = data.get('text2', '')
        
        if not text1 or not text2:
            return jsonify({'error': 'Kedua teks harus diisi'}), 400
        
        # Hitung similarity
        similarity_score = calculate_similarity(text1, text2)
        
        # Tentukan status plagiarisme
        if similarity_score >= 0.8:
            status = "Tinggi (Kemungkinan Plagiarisme)"
        elif similarity_score >= 0.5:
            status = "Sedang (Perlu Pemeriksaan Lebih Lanjut)"
        else:
            status = "Rendah (Kemungkinan Original)"
        
        response = {
            'similarity_score': round(similarity_score * 100, 2),
            'status': status,
            'details': f"Tingkat kesamaan antara kedua teks adalah {round(similarity_score * 100, 2)}%"
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)