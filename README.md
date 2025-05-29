# Essay Automatic Checker

Essay Automatic Checker is a Python-based grading system for answers to open-ended questions. This harnesses the power of Large Language Model
(Gemini) API extract text and grade the content of a student's answer sheet. Essay Automatic Checker was developed along with an Essay 
Automated Scoring Prototype, in compliance with college-level Design Project course.

## Features

- Monitors a specified directory for new image files
- Uses Large Language Model (Gemini) API to extract text from the image
- Uses Large Language Model (Gemini) API to assign a score based on the question, rubrics, and students' answers
- Sends to input user email a spreadsheet with compilation of information from the input papers

## Setup Instructions

1. Clone repository
2. Install dependencies from requirements_windows.txt
3. Setup sender email and password to EAS_main.py > send_email_with_attachment()
4. Setup own APIs to .env
5. Run EAS_main.py
