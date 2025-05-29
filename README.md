# Essay Automatic Checker

This project is a Python-based essay grading system using OCR and Large Language Model (Gemini) API, developed along  
with an Automated Essay Checker Prototype in compliance with college-level Design Project course.

## Features

- Monitors a specified directory for new image files
- Uses Large Language Model (Gemini) API to extract text from the image
- Uses Large Language Model (Gemini) API to assign a score based on the question, rubrics, and students' answers
- Sends a spreadsheet with compilation of information from the input papers

## Setup Instructions

1. Clone repository
2. Install dependencies from requirements_windows.txt
3. Input sender email and password to EAS_main.py > send_email_with_attachment()
4. Input own APIs to .env
5. Run EAS_main.py
