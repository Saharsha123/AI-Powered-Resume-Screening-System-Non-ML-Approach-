import google.generativeai as genai
import re
import ast
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)

# Model is configured in app.py, so we only define it here
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# -------------------- Custom Exception for Float-NoneType Comparison Error --------------------
class FloatNoneComparisonError(Exception):
    """Custom exception for float-NoneType comparison errors."""
    pass

# -------------------- Helpers: Extract Python Dict/List from LLM Output --------------------
def extract_dict_from_text(text):
    """Extract and safely parse a Python dictionary from text."""
    cleaned = re.sub(r"(?:python)?", "", text).replace("", "").strip()
    match = re.search(r"\{[\s\S]*?\}", cleaned)
    if match:
        try:
            return ast.literal_eval(match.group())
        except Exception as e:
            logger.error(f"Error parsing dict: {e}")
            return None
    logger.warning("No dictionary found.")
    return None

def extract_list_from_text(text):
    """Extract and safely parse a Python list from text."""
    cleaned = re.sub(r"(?:python)?", "", text).replace("", "").strip()
    match = re.search(r"\[[\s\S]*?\]", cleaned)
    if match:
        try:
            return ast.literal_eval(match.group())
        except Exception as e:
            logger.error(f"Error parsing list: {e}")
            return None
    logger.warning("No list found.")
    return None

# -------------------- Normalize Extracted Data --------------------
def normalize_jd_experience(jd_exp):
    """Normalize JD experience fields to lowercase."""
    if jd_exp and "fields" in jd_exp:
        jd_exp["fields"] = [field.lower().strip() for field in jd_exp["fields"] if field]
    # Ensure min_years and max_years are numerical or None
    if jd_exp:
        jd_exp["min_years"] = float(jd_exp["min_years"]) if jd_exp.get("min_years") is not None else 0
        jd_exp["max_years"] = float(jd_exp["max_years"]) if jd_exp.get("max_years") is not None else None
    logger.info(f"Normalized JD experience (fields to lowercase, years to float): {jd_exp}")
    return jd_exp

def normalize_resume_experience(resume_exp):
    """Normalize resume experience fields to lowercase."""
    for entry in resume_exp:
        if entry.get("field"):
            entry["field"] = entry["field"].lower().strip()
        if entry.get("title"):
            entry["title"] = entry["title"].lower().strip()
        # Ensure years is a float
        if entry.get("years") is not None:
            entry["years"] = float(entry["years"])
        else:
            entry["years"] = 0.0
    logger.info(f"Normalized resume experience (fields and titles to lowercase, years to float): {resume_exp}")
    return resume_exp

# -------------------- Extract Experience Requirement from Job Description --------------------
def extract_jd_experience(jd_text):
    prompt = f"""
Extract the experience requirement from the following job description.   
Return only a Python dictionary with:
- required: true or false
- min_years: minimum number of years required (int or float)
- max_years: optional max years (or null)
- fields: list of skills or domains, like ["Python", "Django"]
Give just the raw Python dictionary without triple backticks or code formatting and explanation.
Job Description:
\"\"\"{jd_text}\"\"\"
"""
    response = model.generate_content(prompt)
    logger.debug(f"RAW JD RESPONSE: {response.text}")
    jd_exp = extract_dict_from_text(response.text)
    return normalize_jd_experience(jd_exp)

# -------------------- Extract Work Experience from Resume --------------------
def extract_resume_experience(resume_text):
    prompt = f"""
Extract the candidate's work experience from the resume below.
Return a Python list of dictionaries. Each dictionary must contain:
- title: role title (or null)
- years: number of years of experience (float)
- field: technology/domain (e.g. "Django", "Python", "API", or null)
If total experience is mentioned, include it too with title and field set to null.
Give just the raw Python dictionary without triple backticks or code formatting and explanation.
Resume:
\"\"\"{resume_text}\"\"\"
"""
    response = model.generate_content(prompt)
    logger.debug(f"RAW RESUME RESPONSE: {response.text}")
    resume_exp = extract_list_from_text(response.text)
    return normalize_resume_experience(resume_exp)

# -------------------- Normalization & Matching Utilities --------------------
def normalize_field_name(field):
    return field.lower() if field else ""

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def fields_similar(field1, field2, threshold=0.7):
    if not field1 or not field2:
        return False
    return similar(field1, field2) > threshold

# -------------------- Experience Evaluation --------------------
def evaluate_experience(jd_exp, resume_exp, use_fuzzy_matching=True):
    if not jd_exp:
        return False
    if not jd_exp.get("required", False):
        return True
    if not resume_exp:
        return False

    jd_min = jd_exp.get("min_years", 0)
    jd_max = jd_exp.get("max_years", float('inf'))
    jd_fields = jd_exp.get("fields", [])

    total_exp = sum(exp.get("years", 0) for exp in resume_exp)

    # Handle None for jd_max explicitly
    if jd_max is None:
        jd_max = float('inf')

    logger.debug(f"Evaluating experience: jd_min={jd_min}, total_exp={total_exp}, jd_max={jd_max}")
    if total_exp < jd_min or total_exp > jd_max:
        logger.debug(f"Experience evaluation failed: total_exp ({total_exp}) not in range [{jd_min}, {jd_max}]")
        return False

    if jd_fields:
        found = False
        for jd_field in jd_fields:
            for entry in resume_exp:
                res_field = normalize_field_name(entry.get("field"))
                if use_fuzzy_matching:
                    if fields_similar(jd_field, res_field):
                        found = True
                        break
                else:
                    if jd_field.lower() in res_field:
                        found = True
                        break
            if found:
                break
        if not found:
            logger.debug(f"Experience evaluation failed: no matching fields found. JD fields={jd_fields}")
            return False

    logger.debug("Experience evaluation passed")
    return True

# -------------------- Experience Field-Wise Matcher --------------------
def match_experience(jd, resume_experience):
    required_fields = jd.get('fields', [])
    min_years = jd.get('min_years', 0)

    # Track total years of experience for each required field
    field_years = {field.lower(): 0 for field in required_fields}

    for exp in resume_experience:
        exp_field = (exp.get('field') or '').lower()
        exp_years = exp.get('years', 0)

        for req_field in required_fields:
            if req_field.lower() in exp_field:
                field_years[req_field.lower()] += exp_years

    # Debug output
    logger.info(f"Field-wise Experience Accumulated: {field_years}")

    # Check if each required field meets the minimum years
    for field, total_years in field_years.items():
        if total_years < min_years:
            logger.debug(f"Field-wise match failed: {field} has {total_years} years, required {min_years}")
            return False

    logger.debug("Field-wise match passed")
    return True

# -------------------- Experience Scoring --------------------
def score_experience_match(jd_exp, resume_exp, use_fuzzy_matching=True):
    """
    Scores how well the resume experience matches the JD requirements.
    Returns a score between 0 and 100.
    """
    if not jd_exp or not resume_exp:
        logger.debug("JD or resume experience missing, score=0")
        return 0.0

    jd_min = jd_exp.get("min_years", 0)
    jd_max = jd_exp.get("max_years", float("inf"))
    jd_fields = jd_exp.get("fields", [])
    required = jd_exp.get("required", False)

    # Handle None for jd_max explicitly
    if jd_max is None:
        jd_max = float('inf')

    # Score components
    score = 0
    max_score = 100

    # --- 1. Score for Total Experience Match (30 pts) ---
    total_exp = sum(exp.get("years", 0) for exp in resume_exp)

    logger.debug(f"Scoring experience: jd_min={jd_min}, total_exp={total_exp}, jd_max={jd_max}")

    try:
        # Split the comparison to handle None explicitly
        meets_min = total_exp >= jd_min
        meets_max = total_exp <= jd_max if jd_max != float('inf') else True

        if meets_min and meets_max:
            score += 30
            logger.debug("Experience meets min and max requirements, awarded 30 points")
        elif total_exp > jd_max and jd_max != float('inf'):
            score += 20  # reward for exceeding even if not ideal
            logger.debug("Experience exceeds max, awarded 20 points")
        elif total_exp >= jd_min * 0.8:
            score += 15  # partial credit
            logger.debug("Experience close to min requirement, awarded 15 points")
    except TypeError as e:
        logger.error(f"TypeError in experience comparison: {str(e)}")
        if "not supported between instances of 'float' and 'NoneType'" in str(e):
            raise FloatNoneComparisonError("Unable to compare experience years due to missing or invalid data in JD or resume.")
        raise

    # --- 2. Score for Matching Required Fields (70 pts) ---
    field_score = 0
    if jd_fields:
        matched_fields = 0
        for jd_field in jd_fields:
            for exp in resume_exp:
                exp_field = normalize_field_name(exp.get("field"))
                if use_fuzzy_matching and fields_similar(jd_field, exp_field):
                    matched_fields += 1
                    break
                elif jd_field.lower() in exp_field:
                    matched_fields += 1
                    break

        field_score = (matched_fields / len(jd_fields)) * 70
        score += field_score
        logger.debug(f"Field score: {field_score} (matched {matched_fields}/{len(jd_fields)} fields)")
    else:
        # If no specific fields required, award full field score
        score += 70
        logger.debug("No specific fields required, awarded 70 points for fields")

    # --- Return Rounded Score ---
    final_score = round(min(score, max_score), 2)
    logger.debug(f"Final experience score: {final_score}")
    return final_score