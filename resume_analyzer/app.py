from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, TextAreaField, FileField, BooleanField
from wtforms.validators import DataRequired, EqualTo
from werkzeug.utils import secure_filename
import os
import logging
from utils.skill_extract import evaluate_resume, extract_skills_from_expression
from utils.db_operations import init_db, register_user, verify_user, save_result, get_results
from utils.education_extract import education_level_match
from utils.exper_test import evaluate_experience, score_experience_match, FloatNoneComparisonError
import google.generativeai as genai
from dotenv import load_dotenv
import fitz  # PyMuPDF
import docx
from PIL import Image
import pytesseract
import io
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time
import ast
import re

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)
logger.info(f"Loaded .env file from: {os.path.abspath('.env')}")

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads/resumes'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}  # Support PDF, DOCX, and TXT

# Load Gemini API key from environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not set in environment variables.")
    raise ValueError("GEMINI_API_KEY must be set in environment variables.")
genai.configure(api_key=GEMINI_API_KEY)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize database
try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise

# Define Forms with Flask-WTF
class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    confirm_password = PasswordField('confirm_password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

class UploadForm(FlaskForm):
    job_desc = TextAreaField('job_desc', validators=[DataRequired()])
    resume = FileField('resume', validators=[DataRequired()])
    experience_required = BooleanField('Experience evaluation should be done (or no experience required)')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    """
    Extract text from a file based on its extension.
    
    Args:
        file_path (str): Path to the file.
        
    Returns:
        str: Extracted text or empty string if extraction fails.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".pdf":
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                page_text = page.get_text()
                if page_text.strip():
                    text += page_text + "\n"
            doc.close()
            if text.strip():
                return text

            # If no text is extracted, assume it's a scanned PDF and try OCR
            logger.info(f"No text found in PDF {file_path}. Attempting OCR...")
            text = ""
            doc = fitz.open(file_path)
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                page_text = pytesseract.image_to_string(img)
                text += page_text + "\n"
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {str(e)}")
            return ""
    elif ext == ".docx":
        try:
            doc = docx.Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            logger.error(f"Error reading DOCX {file_path}: {str(e)}")
            return ""
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading TXT file {file_path}: {str(e)}")
            return ""
    else:
        logger.error(f"Unsupported file format: {ext}")
        return ""

# Gemini API model
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# Retry decorator for Gemini API calls
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(genai.types.BlockedPromptException),
    before_sleep=lambda retry_state: logger.info(f"Retrying Gemini API call (attempt {retry_state.attempt_number}) after delay...")
)
def safe_gemini_call(prompt):
    try:
        # Add a delay to avoid hitting rate limits
        time.sleep(30)  # Increased to 30 seconds to ensure < 2 RPM
        response = model.generate_content(prompt)
        return response.text.strip()
    except genai.types.BlockedPromptException as e:
        if "429" in str(e):
            logger.warning(f"Gemini API 429 error: {str(e)}")
            raise
        else:
            logger.error(f"Gemini API error: {str(e)}")
            raise

# Extract skills, education, and experience from job description in one call
def extract_jd_data(job_desc):
    prompt = f"""
    From the job description below, extract the following in a single Python dictionary:
    - skills_expression: Boolean expression of required skills (e.g., '"Skill1" AND ("Skill2" OR "Skill3")')
    - education: Dictionary with education requirements for each level (10th, PU, UG, PG), each with 'required' (boolean), 'degree', and 'cgpa' (if applicable)
    - experience: Dictionary with experience requirements (required: boolean, min_years: int/float, max_years: int/float/None, fields: list of skills/domains)
    Return ONLY the raw Python dictionary as a string (e.g., {{'key': 'value'}}). Do NOT include triple backticks, explanations, or any other text outside the dictionary.

    Job Description:
    \"\"\"{job_desc}\"\"\"
    """
    try:
        response = safe_gemini_call(prompt)
        logger.info(f"JD extraction response: {response}")
        # Clean the response: remove triple backticks, newlines, and extract the dictionary
        response = response.strip()
        # Remove triple backticks if present
        response = re.sub(r'```(?:python)?\n?', '', response)
        # Extract the dictionary using regex (match content between { and })
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            response = match.group(0)
        else:
            raise ValueError("No valid dictionary found in response")
        logger.info(f"Cleaned JD response: {response}")
        return ast.literal_eval(response)
    except Exception as e:
        logger.error(f"Error extracting JD data: {str(e)}")
        return None

# Extract skills, education, and experience from resume in one call
def extract_resume_data(resume_text):
    prompt = f"""
    From the resume content below, extract the following in a single Python dictionary:
    - skills: Set of skills (e.g., {{'Skill1', 'Skill2'}})
    - education: List of dictionaries with educational qualifications (level: e.g., '10th', 'PU', 'UG', 'PG'; degree; cgpa)
    - experience: List of dictionaries with work experience (title: str/None, years: float, field: str/None)
    Return ONLY the raw Python dictionary as a string (e.g., {{'key': 'value'}}). Do NOT include triple backticks, explanations, or any other text outside the dictionary.

    Resume:
    \"\"\"{resume_text}\"\"\"
    """
    try:
        response = safe_gemini_call(prompt)
        logger.info(f"Resume extraction response: {response}")
        # Clean the response: remove triple backticks, newlines, and extract the dictionary
        response = response.strip()
        # Remove triple backticks if present
        response = re.sub(r'```(?:python)?\n?', '', response)
        # Extract the dictionary using regex (match content between { and })
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            response = match.group(0)
        else:
            raise ValueError("No valid dictionary found in response")
        logger.info(f"Cleaned resume response: {response}")
        return ast.literal_eval(response)
    except Exception as e:
        logger.error(f"Error extracting resume data: {str(e)}")
        return None

# Education evaluation functions (simplified, moved from education_extract.py)
degree_rank = {
    "phd": 4, "mtech": 3, "msc": 3, "masters": 3,
    "btech": 2, "bsc": 2, "bachelor": 2,
    "diploma": 1, "pu": 0.5, "12th": 0.5, "puc": 0.5,
    "10th": 0.4, "sslc": 0.4
}

EDUCATION_LEVEL_WEIGHTS = {"10th": 0.1, "PU": 0.2, "UG": 0.5, "PG": 0.2}

def normalize_degree_name(degree):
    if not degree:
        return None
    degree = degree.lower()
    for key in degree_rank:
        if key in degree:
            return key
    return None

def parse_cgpa(cgpa):
    if not cgpa:
        return None
    try:
        cgpa = str(cgpa).strip().replace('%', '')
        return float(cgpa)
    except:
        return None

def preprocess_resume_data(resume_data):
    for entry in resume_data:
        entry["cgpa"] = parse_cgpa(entry.get("cgpa"))
    return resume_data

def get_resume_entry(resume_list, level_name):
    for entry in resume_list:
        if entry["level"].lower() == level_name.lower():
            return entry
    return None

def evaluate_education_score(jd_education, resume_education):
    try:
        resume_education = preprocess_resume_data(resume_education)
        score = 0.0
        total_weight = 0.0

        for level, weight in EDUCATION_LEVEL_WEIGHTS.items():
            jd_entry = jd_education.get(level, {"required": False})
            resume_entry = get_resume_entry(resume_education, level)

            total_weight += weight
            if education_level_match(jd_entry, resume_entry, level):
                score += weight

        match_percentage = round((score / total_weight) * 100, 2) if total_weight > 0 else 0.0
        return match_percentage
    except Exception as e:
        logger.error(f"Error evaluating education score: {str(e)}")
        return 0.0

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        try:
            if verify_user(username, password):
                session['username'] = username
                logger.info(f"User {username} logged in successfully.")
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials')
                logger.warning(f"Failed login attempt for username: {username}")
        except Exception as e:
            flash('An error occurred during login.')
            logger.error(f"Login error for {username}: {e}")
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        try:
            if register_user(username, password):
                flash('Registration successful! Please login.')
                logger.info(f"User {username} registered successfully.")
                return redirect(url_for('login'))
            else:
                flash('Username already exists')
                logger.warning(f"Registration failed: Username {username} already exists.")
        except Exception as e:
            flash('An error occurred during registration.')
            logger.error(f"Registration error for {username}: {e}")
    return render_template('register.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        logger.warning("Unauthorized access to dashboard.")
        return redirect(url_for('login'))
    try:
        results = get_results(session['username'])
        formatted_results = [
            {
                'id': result[0],
                'job_description': result[1],
                'resume_file': result[2],
                'skills': result[3],
                'result': result[4],
                'matches': result[5],
                'date': result[6],
                'education_result': result[7],
                'education_score': result[8],
                'experience_result': result[9],
                'experience_score': result[10]
            } for result in results
        ]
        logger.info(f"Dashboard accessed by {session['username']} with {len(formatted_results)} results.")
        logger.debug(f"Formatted results: {formatted_results}")
        return render_template('dashboard.html', results=formatted_results)
    except Exception as e:
        flash('An error occurred while fetching results.')
        logger.error(f"Dashboard error for {session['username']}: {e}")
        return redirect(url_for('login'))

@app.route('/details/<int:result_id>')
def details(result_id):
    if 'username' not in session:
        logger.warning("Unauthorized access to details page.")
        return redirect(url_for('login'))
    try:
        results = get_results(session['username'])
        # Find the result with the matching ID
        result = next((r for r in results if r[0] == result_id), None)
        if not result:
            flash('Result not found.')
            logger.warning(f"Result ID {result_id} not found for user {session['username']}.")
            return redirect(url_for('dashboard'))

        formatted_result = {
            'id': result[0],
            'job_description': result[1],
            'resume_file': result[2],
            'skills': result[3],
            'result': result[4],
            'matches': result[5],
            'date': result[6],
            'education_result': result[7],
            'education_score': result[8],
            'experience_result': result[9],
            'experience_score': result[10]
        }

        # Calculate overall score dynamically
        scores = [score for score in [formatted_result['matches'], formatted_result['education_score'], formatted_result['experience_score']] if score is not None]
        overall_score = sum(scores) / len(scores) if scores else 0.0

        logger.info(f"Details page accessed for result ID {result_id} by {session['username']}.")
        return render_template('details.html', result=formatted_result, overall_score=overall_score)
    except Exception as e:
        flash('An error occurred while fetching the details.')
        logger.error(f"Details page error for result ID {result_id}: {e}")
        return redirect(url_for('dashboard'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        logger.warning("Unauthorized access to upload page.")
        return redirect(url_for('login'))
    
    form = UploadForm()
    if request.method == 'POST' and form.validate_on_submit():
        job_desc = form.job_desc.data
        file = form.resume.data
        experience_required = form.experience_required.data

        logger.info(f"Received job description: {job_desc[:100]}...")
        logger.info(f"Experience evaluation required: {experience_required}")

        if not file or not allowed_file(file.filename):
            logger.warning("Invalid file type uploaded.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Invalid file type. Please upload a PDF, DOCX, or TXT file.'}), 400
            flash('Invalid file type. Please upload a PDF, DOCX, or TXT file.')
            return redirect(request.url)

        timestamp = int(time.time())
        base_filename, ext = os.path.splitext(secure_filename(file.filename))
        filename = f"{base_filename}_{timestamp}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(file_path)
            if not os.path.exists(file_path):
                logger.error(f"File {file_path} not found after saving.")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Failed to save file.'}), 500
                flash('Failed to save file.')
                return redirect(request.url)
            logger.info(f"File {filename} saved successfully at {file_path} for user {session['username']}.")
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Failed to save file.'}), 500
            flash('Failed to save file.')
            return redirect(request.url)

        try:
            # Extract text from the file
            resume_text = extract_text_from_file(file_path)
            if not resume_text.strip():
                logger.error(f"Failed to extract text from {filename}: No text found.")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Failed to extract text from the file. Please upload a valid file.'}), 400
                flash("Failed to extract text from the file. Please upload a valid file.")
                return redirect(request.url)
            logger.info(f"Text extracted from {filename}: {resume_text[:100]}...")
            
            # Extract all JD data in one call
            jd_data = extract_jd_data(job_desc)
            if not jd_data:
                raise Exception("Failed to extract job description data")
            skills_expression = jd_data.get("skills_expression", "")
            jd_education = jd_data.get("education", {})
            jd_exp = jd_data.get("experience", {})

            # Extract all resume data in one call
            resume_data = extract_resume_data(resume_text)
            if not resume_data:
                raise Exception("Failed to extract resume data")
            resume_skills = resume_data.get("skills", set())
            resume_education = resume_data.get("education", [])
            resume_exp = resume_data.get("experience", [])

            # Process skills
            skills_result, match_count = evaluate_resume(skills_expression, resume_skills)
            logger.info(f"Skills analysis completed for {filename}: Result={skills_result}, Matches={match_count}%")
            
            # Process experience only if checkbox is checked
            experience_result = True  # Default to True (neutral for overall result)
            experience_score = None   # Will exclude from overall score if not evaluated
            if experience_required:
                try:
                    experience_result = evaluate_experience(jd_exp, resume_exp)
                    experience_score = score_experience_match(jd_exp, resume_exp)
                    logger.info(f"Experience analysis completed for {filename}: Result={experience_result}, Score={experience_score}%")
                except FloatNoneComparisonError as e:
                    logger.error(f"Experience analysis failed for {filename}: {str(e)}")
                    error_message = "Analysis stopped: Experience years in the job description or resume are missing or invalid. Please ensure both specify valid numerical years of experience."
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': str(e), 'message': error_message}), 400
                    flash(error_message)
                    return redirect(request.url)
            else:
                logger.info(f"Experience evaluation skipped for {filename} as per user selection.")

            # Process education
            education_result = all(
                education_level_match(jd_education.get(level, {"required": False}), 
                                    get_resume_entry(resume_education, level), level)
                for level in ["10th", "PU", "UG", "PG"]
            )
            education_score = evaluate_education_score(jd_education, resume_education)
            logger.info(f"Education analysis completed for {filename}: Result={education_result}, Score={education_score}%")
            
            # Combine results
            overall_result = "Pass" if skills_result and education_result and experience_result else "Fail"
            # Calculate overall score dynamically based on evaluated components
            scores = [score for score in [match_count, education_score, experience_score] if score is not None]
            overall_score = sum(scores) / len(scores) if scores else 0.0
            
            # Save result to database
            save_result(
                session['username'], 
                job_desc, 
                filename, 
                ', '.join(resume_skills), 
                overall_result, 
                match_count,
                education_result,
                education_score,
                experience_result if experience_required else None,
                experience_score if experience_required else None
            )
            logger.info(f"Result saved to database for user {session['username']}.")
            
            # If AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'result': overall_result,
                    'skills': list(extract_skills_from_expression(skills_expression)),
                    'resume_skills': list(resume_skills),
                    'match_count': match_count,
                    'skills_length': len(extract_skills_from_expression(skills_expression)),
                    'education_result': education_result,
                    'education_score': education_score,
                    'experience_result': experience_result if experience_required else None,
                    'experience_score': experience_score if experience_required else None,
                    'overall_score': overall_score,
                    'experience_evaluated': experience_required
                })
            
            # Otherwise, render the template
            return render_template('upload.html', form=form, result=overall_result, 
                                skills=list(extract_skills_from_expression(skills_expression)),
                                resume_skills=list(resume_skills), match_count=match_count, 
                                education_result=education_result, education_score=education_score,
                                experience_result=experience_result if experience_required else None,
                                experience_score=experience_score if experience_required else None,
                                overall_score=overall_score, experience_evaluated=experience_required)
        except Exception as e:
            logger.error(f"Analysis failed for {filename}: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Analysis failed due to API quota limits or other errors. Please try again later.'}), 500
            flash('Analysis failed due to API quota limits or other errors. Please try again later.')
            return redirect(request.url)
    
    return render_template('upload.html', form=form)

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.pop('username', None)
    logger.info(f"User {username} logged out.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)