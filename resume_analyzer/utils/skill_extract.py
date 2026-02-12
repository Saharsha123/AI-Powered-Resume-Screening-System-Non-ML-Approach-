import google.generativeai as genai
import re
import logging

logger = logging.getLogger(__name__)

# Model is configured in app.py, so we only define it here
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

def generate_boolean_expression(job_desc):
    """Generate a Boolean expression of required skills from the job description."""
    prompt = f"""
    From the job description below, return only the Boolean expression of required and preferred skills using AND/OR that is compatible to evaluate in Python. The expression should be in the format: "Skill1" AND ("Skill2" OR "Skill3"). Do not add any extra explanation, just the equation.

    Job Description:
    \"\"\"{job_desc}\"\"\"
    """
    try:
        response = model.generate_content(prompt)
        expression = response.text.strip()
        if not expression:
            logger.warning("No skills expression extracted from JD, returning 'False'")
            return 'False'
        logger.info(f"Generated boolean expression: {expression}")
        return expression
    except Exception as e:
        logger.error(f"Error generating boolean expression: {str(e)}")
        return 'False'

def extract_skills(resume_text):
    """Extract a set of skills from the resume text, normalizing to lowercase and trimming spaces."""
    prompt = f"""
    From the resume content below, return only the set of skills that the applicant has. The expression should be in the format: {{'Skill1', 'Skill2', 'skill3'}}. Do not add any extra explanation, just the set. Note: Don't add comma after the last element and use exclusively flower brackets.

    Resume:
    \"\"\"{resume_text}\"\"\"
    """
    try:
        response = model.generate_content(prompt)
        # Evaluate the response, trim spaces, and normalize to lowercase
        skills = eval(response.text.strip())
        # Filter out None, empty strings, and non-string values
        skills = [skill for skill in skills if skill and isinstance(skill, str)]
        normalized_skills = {skill.strip().lower() for skill in skills}
        logger.info(f"Extracted resume skills (normalized to lowercase, trimmed): {normalized_skills}")
        return normalized_skills
    except Exception as e:
        logger.error(f"Error extracting skills from resume: {str(e)}")
        return set()

def evaluate_resume(skills_expression, resume_skills):
    """Evaluate if the resume matches the job description based on the Boolean expression, using case-insensitive comparison."""
    if not skills_expression or skills_expression == 'False':
        logger.info("No skills expression provided or expression is 'False'; defaulting to False, 0% match.")
        return False, 0.0
    
    try:
        # Extract required skills and normalize them upfront
        required_skills = {token.strip('"').strip().lower() for token in re.findall(r'"([^"]+)"', skills_expression) if token.strip('"').strip()}
        logger.info(f"Required skills (normalized to lowercase, trimmed): {required_skills}")

        # Ensure resume_skills are normalized (should already be, but double-check)
        resume_skills = {skill.strip().lower() for skill in resume_skills if skill and isinstance(skill, str)}
        logger.info(f"Resume skills (ensured normalized to lowercase, trimmed): {resume_skills}")

        # Tokenize the skills expression
        skills_tokens = re.findall(r'"[^"]+"|\(|\)|\b(?:and|or|not)\b', skills_expression, re.IGNORECASE)
        if not skills_tokens:
            logger.info("No tokens extracted from skills expression; defaulting to False, 0% match.")
            return False, 0.0

        # Normalize tokens for evaluation
        normalized_tokens = []
        for token in skills_tokens:
            if token.startswith('"') and token.endswith('"'):
                # Strip quotes, trim, and normalize skill to lowercase
                skill = token.strip('"').strip().lower()
                normalized_tokens.append(skill)
            else:
                # Keep operators as lowercase for consistency
                normalized_tokens.append(token.lower())
        logger.info(f"Tokenized skills expression (normalized to lowercase, trimmed): {normalized_tokens}")

        # Operator precedence
        precedence = {'not': 3, 'and': 2, 'or': 1}

        # Stacks for operands and operators
        operand_stack = []
        operator_stack = []

        def apply_operator(op):
            if op == 'not':
                if not operand_stack:
                    logger.error("Operand stack empty when applying 'not' operator")
                    raise ValueError("Operand stack empty for 'not' operator")
                operand = operand_stack.pop()
                operand_stack.append(not operand)
            else:
                if len(operand_stack) < 2:
                    logger.error(f"Operand stack has insufficient elements for '{op}' operator: {operand_stack}")
                    raise ValueError(f"Insufficient operands for '{op}' operator")
                right = operand_stack.pop()
                left = operand_stack.pop()
                if op == 'and':
                    operand_stack.append(left and right)
                elif op == 'or':
                    operand_stack.append(left or right)

        # Evaluate expression
        for token in normalized_tokens:
            if token in {'and', 'or', 'not'}:
                while (operator_stack and operator_stack[-1] != '(' and 
                       precedence.get(operator_stack[-1], 0) >= precedence.get(token, 0)):
                    apply_operator(operator_stack.pop())
                operator_stack.append(token)
            elif token == '(':
                operator_stack.append(token)
            elif token == ')':
                while operator_stack and operator_stack[-1] != '(':
                    apply_operator(operator_stack.pop())
                if operator_stack:
                    operator_stack.pop()  # remove '('
                else:
                    logger.error("Mismatched parentheses: closing parenthesis without matching opening")
                    raise ValueError("Mismatched parentheses")
            else:
                # Compare token (lowercase) with resume_skills (lowercase)
                is_present = token in resume_skills
                logger.debug(f"Evaluating skill '{token}': {'Present' if is_present else 'Not present'} in resume_skills")
                operand_stack.append(is_present)

        # Apply remaining operators
        while operator_stack:
            if operator_stack[-1] == '(':
                logger.error("Mismatched parentheses: unclosed opening parenthesis")
                raise ValueError("Mismatched parentheses")
            apply_operator(operator_stack.pop())

        # Final evaluation result
        if not operand_stack:
            logger.error("Operand stack empty after evaluation")
            raise ValueError("No result after evaluation")
        result = operand_stack.pop()
        logger.info(f"Evaluation result: {result}")

        # Calculate match count as a percentage
        match_count = len(required_skills & resume_skills) / len(required_skills) * 100 if required_skills else 0.0
        logger.info(f"Match count calculation: Intersection={required_skills & resume_skills}, Match Percentage={match_count}")

        logger.info(f"Evaluated resume: Result={result}, Match Percentage={match_count}")
        return result, round(match_count, 2)
    except Exception as e:
        logger.error(f"Error evaluating resume: {str(e)}")
        return False, 0.0

def extract_skills_from_expression(expression):
    """Extract required skills from the Boolean expression, normalizing to lowercase."""
    if not expression:
        return set()
    skills = {token.strip('"').strip().lower() for token in re.findall(r'"([^"]+)"', expression) if token.strip('"').strip()}
    logger.info(f"Extracted skills from expression (normalized to lowercase, trimmed): {skills}")
    return skills

def calculate_match_score(required_skills, resume_skills):
    """Calculate the match score as a percentage, using case-insensitive comparison."""
    if not required_skills:
        logger.info("No required skills; match score is 0%.")
        return 0.0
    # Ensure both sets are normalized (should already be, but double-check)
    required_skills = {skill.strip().lower() for skill in required_skills if skill and isinstance(skill, str)}
    resume_skills = {skill.strip().lower() for skill in resume_skills if skill and isinstance(skill, str)}
    matched_skills = required_skills & resume_skills
    match_score = len(matched_skills) / len(required_skills) * 100
    logger.info(f"Calculated match score: {match_score}% (Matched: {matched_skills}, Required: {required_skills})")
    return round(match_score, 2)