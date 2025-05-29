# Essay Automatic Checker

**Essay Automatic Checker** is a Python-based grading system for open-ended questions. It uses the **Gemini Large Language Model (LLM)** API to extract and evaluate student responses from scanned answer sheets. This system was developed alongside a camera-based automated paper feeding and capturing prototype as part of our college-level Design Project course.

## Features

- Monitors a specified directory for new image files
- Uses Gemini LLM API for:
  - OCR (extracting text from answer sheets)
  - Automated grading based on question, rubric, and student answers
- Compiles results into a spreadsheet
- Automatically sends the spreadsheet to a user-input email address

## Setup Instructions

1. Clone the repository:

   git clone https://github.com/jsphmlln/Essay-Automatic-Checker.git
   cd Essay-Automatic-Checker

2. Install dependencies:

   pip install -r requirements_windows.txt

3. Set up sender email credentials:

   Open `EAS_main.py`, and update the `send_email_with_attachment()` function with:
   - Your sender email address
   - An app-specific password (not your regular password)

4. Edit the `.env` file in the project root folder to add your API Keys

5. Run the main script:

   python main.py
