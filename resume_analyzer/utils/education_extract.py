import google.generativeai as genai
import re
from difflib import SequenceMatcher
import os
import logging

logger = logging.getLogger(__name__)

# Configure Gemini (API key is set in app.py, so we only define the model here)
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# ------------------------ Degree Rank Mapping ------------------------

degree_rank = {
    "phd": 4,
    "mtech": 3, "msc": 3, "masters": 3,
    "btech": 2, "bsc": 2, "bachelor": 2,
    "diploma": 1,
    "pu": 0.5, "12th": 0.5, "puc": 0.5,
    "10th": 0.4, "sslc": 0.4
}

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
        # Normalize degree and level to lowercase
        if entry.get("degree"):
            entry["degree"] = entry["degree"].lower()
        if entry.get("level"):
            entry["level"] = entry["level"].lower()
    logger.info(f"Preprocessed resume data (normalized to lowercase): {resume_data}")
    return resume_data

def preprocess_jd_data(jd_data):
    for level, entry in jd_data.items():
        if entry.get("degree"):
            entry["degree"] = entry["degree"].lower()
    logger.info(f"Preprocessed JD data (normalized to lowercase): {jd_data}")
    return jd_data

def get_resume_entry(resume_list, level_name):
    for entry in resume_list:
        if entry["level"].lower() == level_name.lower():
            return entry
    return None

# ------------------------ Optional: Fuzzy Degree Matching ------------------------

USE_FUZZY_MATCHING = True

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def degrees_similar(degree1, degree2, threshold=0.7):
    if not degree1 or not degree2:
        return False
    return similar(degree1, degree2) > threshold

# ------------------------ Education Match Function ------------------------

def education_level_match(jd_entry, resume_entry, level):
    if not jd_entry.get("required", False):
        return True
    if not resume_entry:
        return False

    if level in ["UG", "PG"]:
        jd_degree = normalize_degree_name(jd_entry.get("degree"))
        resume_degree = normalize_degree_name(resume_entry.get("degree"))
        if not jd_degree or not resume_degree:
            return False
        if degree_rank.get(resume_degree, 0) < degree_rank.get(jd_degree, 0):
            return False

        if jd_entry.get("degree"):
            if USE_FUZZY_MATCHING:
                if not degrees_similar(jd_entry["degree"], resume_entry["degree"]):
                    return False
            else:
                if jd_entry["degree"].lower() not in resume_entry["degree"].lower():
                    return False

    jd_cgpa = jd_entry.get("cgpa")
    resume_cgpa = resume_entry.get("cgpa")

    if jd_cgpa is not None:
        logger.debug(f"Comparing CGPA for level {level}: JD CGPA = {jd_cgpa}, Resume CGPA = {resume_cgpa}")
        if resume_cgpa is None:
            logger.debug(f"Resume CGPA is None for level {level}, failing match")
            return False
        if resume_cgpa < jd_cgpa:
            logger.debug(f"Resume CGPA {resume_cgpa} is less than JD CGPA {jd_cgpa} for level {level}, failing match")
            return False

    return True

# ------------------------ Main Evaluation ------------------------

EDUCATION_LEVEL_WEIGHTS = { 
    "10th": 0.1,
    "PU": 0.2,
    "UG": 0.5,
    "PG": 0.2
}

def evaluate_education(job_desc, resume_text):
    # Extract JD education criteria
    jd_prompt = f"""
    From the job description below, extract the education requirements for each level (10th, PU, UG, PG).
    Format the output as a Python dictionary, with each level containing a "required" flag, a "degree" if applicable, and a "cgpa" if applicable. Give just the raw Python dictionary without triple backticks or code formatting and explanation.

    Job Description:
    \"\"\"{job_desc}\"\"\"
    """
    response = model.generate_content(jd_prompt)
    jd_criteria = eval(response.text.strip())
    jd_criteria = preprocess_jd_data(jd_criteria)

    # Extract resume educational qualifications
    resume_prompt = f"""
    From the resume content below, extract the educational qualifications (10th, PU, UG, PG).
    Return the result as a list of dictionaries with keys: 'level' (e.g., '10th', 'PU', 'UG', 'PG'), 'degree', and 'cgpa'. Give just the raw Python dictionary without triple backticks or code formatting and explanation.

    Resume:
    \"\"\"{resume_text}\"\"\"
    """
    response = model.generate_content(resume_prompt)
    resume_qualifications = eval(response.text.strip())

    # Evaluate
    resume_qualifications = preprocess_resume_data(resume_qualifications)
    for level in ["10th", "PU", "UG", "PG"]:
        jd_entry = jd_criteria.get(level, {"required": False})
        resume_entry = get_resume_entry(resume_qualifications, level)

        if not education_level_match(jd_entry, resume_entry, level):
            return False
    return True

def evaluate_education_score(job_desc, resume_text):
    # Extract JD education criteria
    jd_prompt = f"""
    From the job description below, extract the education requirements for each level (10th, PU, UG, PG).
    Format the output as a Python dictionary, with each level containing a "required" flag, a "degree" if applicable, and a "cgpa" if applicable. Give just the raw Python dictionary without triple backticks or code formatting and explanation.

    Job Description:
    \"\"\"{job_desc}\"\"\"
    """
    response = model.generate_content(jd_prompt)
    jd_criteria = eval(response.text.strip())
    jd_criteria = preprocess_jd_data(jd_criteria)

    # Extract resume educational qualifications
    resume_prompt = f"""
    From the resume content below, extract the educational qualifications (10th, PU, UG, PG).
    Return the result as a list of dictionaries with keys: 'level' (e.g., '10th', 'PU', 'UG', 'PG'), 'degree', and 'cgpa'. Give just the raw Python dictionary without triple backticks or code formatting and explanation.

    Resume:
    \"\"\"{resume_text}\"\"\"
    """
    response = model.generate_content(resume_prompt)
    resume_qualifications = eval(response.text.strip())

    # Evaluate score
    resume_qualifications = preprocess_resume_data(resume_qualifications)
    score = 0.0
    total_weight = 0.0

    for level, weight in EDUCATION_LEVEL_WEIGHTS.items():
        jd_entry = jd_criteria.get(level, {"required": False})
        resume_entry = get_resume_entry(resume_qualifications, level)

        total_weight += weight
        if education_level_match(jd_entry, resume_entry, level):
            score += weight

    match_percentage = round((score / total_weight) * 100, 2)
    return match_percentage