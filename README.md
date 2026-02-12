# 🧠 AI-Powered Resume Screening System
A professional, transparent, and algorithm-driven resume screening platform that automates candidate shortlisting using Large Language Models (Gemini), Boolean rule evaluation, and Jaccard set-intersection similarity.

## ✨ Features
1. **Intelligent Resume Parsing** - PDF/DOC support with skills, education, and experience extraction
2. **Gemini-Powered Skill Extraction** - Converts job descriptions into structured skill sets
3. **Boolean Logic Engine** - AND/OR/NOT evaluation with operator precedence (Dijkstra's algorithm)
4. **Multi-Stage Filtering** - Skills → Qualification → Experience validation
5. **Jaccard Similarity Scoring** - Efficient scoring system based on the similarity of the content in the resume and Job Description(JD)
6. **Explainable Decisions** - Transparent, traceable evaluation logic
7. **Batch Processing** - Scalable for high-volume screening

## 🎯 Why This Project?
Traditional ATS systems are often black-box solutions. This project provides:
| ✅ Advantages              | ❌ Traditional ATS   |
| -------------------------- |---------------------  |
| Transparent logic          | Black-box decisions   |
| No training data required  | ML model dependency   |
| Lightweight & fast         | Heavy infrastructure  |
| Explainable scoring        | Opaque reasoning      |
| Rule-based consistency     | Algorithmic bias risk |

## 🏗️ System Architecture
```
1. JOB DESCRIPTION INPUT
   ↓
2. Gemini extracts required skills
   ↓
3. Generates Boolean rules (AND/OR/NOT)
   ↓
4. RESUME UPLOAD (PDF/DOC)
   ↓
5. Text extraction from resume
   ↓
6. Gemini extracts candidate skills
   ↓
7. EVALUATION PIPELINE
   ↓
8. QUALIFICATION FILTER (Education/Degree)
   ↓
9. JACCARD SIMILARITY (Skill matching)
   ↓
10. EXPERIENCE VALIDATION (Years/Role)
    ↓
11. FINAL DECISION + EXPLANATION
```

## 🔬 Core Algorithms
### 1. **Dijkstra's Two-Stack Algorithm**
Evaluates Boolean expressions with proper precedence
Time Complexity: O(n)
### 2. **Jaccard Similarity** 
Score = |Job Skills ∩ Resume Skills| / |Job Skills ∪ Resume Skills|
Example: {python,sql} ∩ {python,flask,sql} = 0.5 (50% match)
Time Complexity: O(n + m)
### 3. **Rule-Based Filtering**
- Skill set validation
- Education requirement matching
- Experience verification

## 🛠 Tech Stack
| Component    | Technology                     |
| ------------ | ------------------------------ |
| Backend      | Python, Flask                  |
| Frontend     | HTML, CSS, JavaScript          |
| AI           | Google Gemini API              |
| PDF Parsing  | PyMuPDF                        |
| DOC Parsing  | python-docx                    |
| Logic Engine | Custom Dijkstra implementation |

## 🚀 Quick Start
### Prerequisites
- Python 3.8+
- Gemini API Key
### Installation
```bash
git clone https://github.com/your-username/resume-screening-system.git
cd resume-screening-system
pip install -r requirements.txt
```
### Setup
1. Add your Gemini API key:
```python
import google.generativeai as genai
genai.configure(api_key="YOUR_GEMINI_API_KEY")
```
2. Run the application:
```bash
python app.py
```
3. Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 👥 Authors
- **Harshavardhan N**
- **Koushik Nayaka U**
- **Saharsha**
**Department of Computer Science & Engineering**  
**RV College of Engineering**

## 📜 License
This project is developed for academic and research purposes.
