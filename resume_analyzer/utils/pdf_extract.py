import tkinter as tk
from tkinter import filedialog, messagebox
import fitz  # PyMuPDF for PDF
import docx
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to extract text from PDF
def extract_text_from_pdf(filepath):
    """
    Extract text from a PDF file using PyMuPDF.
    
    Args:
        filepath (str): Path to the PDF file.
        
    Returns:
        str: Extracted text or empty string if extraction fails.
    """
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"PDF file not found at: {filepath}")
        
        logger.info(f"Extracting text from PDF: {filepath}")
        doc = fitz.open(filepath)
        text = ""
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
            else:
                logger.warning(f"No text found on page {page_num} of {filepath}")
        doc.close()
        if not text.strip():
            logger.warning(f"No text extracted from {filepath}. It may be a scanned PDF.")
        return text
    except Exception as e:
        logger.error(f"Error reading PDF {filepath}: {str(e)}")
        return ""

# Function to extract text from DOCX
def extract_text_from_docx(filepath):
    """
    Extract text from a DOCX file using python-docx.
    
    Args:
        filepath (str): Path to the DOCX file.
        
    Returns:
        str: Extracted text or empty string if extraction fails.
    """
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"DOCX file not found at: {filepath}")
        
        logger.info(f"Extracting text from DOCX: {filepath}")
        doc = docx.Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
        if not text.strip():
            logger.warning(f"No text extracted from {filepath}.")
        return text
    except Exception as e:
        logger.error(f"Error reading DOCX {filepath}: {str(e)}")
        return ""

# Function to choose and read resume file
def upload_resume():
    """
    Open a file dialog to select a resume file and extract its text.
    
    Returns:
        str: Extracted text or empty string if extraction fails or no file is selected.
    """
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    file_path = filedialog.askopenfilename(
        title="Select Resume File",
        filetypes=[
            ("PDF files", "*.pdf"),
            ("Word files", "*.docx"),
            ("Text files", "*.txt")
        ]
    )

    if not file_path:
        messagebox.showwarning("No File Selected", "Please select a file.")
        return ""

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        try:
            logger.info(f"Extracting text from TXT: {file_path}")
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()
                if not text.strip():
                    logger.warning(f"No text extracted from {file_path}.")
                return text
        except Exception as e:
            logger.error(f"Error reading TXT file {file_path}: {str(e)}")
            return ""
    else:
        messagebox.showerror("Unsupported Format", "Unsupported file format selected.")
        return ""

# Example usage
if __name__ == "__main__":
    resume_text = upload_resume()
    if resume_text.strip():
        print("Extracted Resume Text:\n", resume_text)
    else:
        print("No text could be extracted.")