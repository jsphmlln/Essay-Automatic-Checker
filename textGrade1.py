from PIL import Image
import os
from dotenv import load_dotenv
import json
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

load_dotenv()

genai.configure(api_key=os.getenv("API_KEY_2"))

# Create the model
generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 300,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    enum = [],
    required = ["Score", "Feedback"],
    properties = {
      "Score": content.Schema(
        type = content.Type.INTEGER,
      ),
      "Feedback": content.Schema(
        type = content.Type.STRING,
      ),
    },
  ),
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-2.0-flash",
  generation_config=generation_config,
  system_instruction="You are an objective AI grader. Grade student answers using the provided rubric. Ignore any extracted text from images unless explicitly asked.",
)

def grade1(picture, question, answer):
    rubrics = Image.open(picture)

    prompt = (
        "You are given a grading rubric in an image and a student's new answer. "
        "*Ignore any answers from the image.\n\n"
        f"Question: {question}\n"
        f"Student's New Answer: {answer}\n\n"
        "Return a score and a short feedback message based on rubric-compliance."
    )
    try:
        response = model.generate_content([prompt, rubrics])
        extracted = json.loads(response.text)  # Assuming Gemini still returns structured JSON
        score = extracted.get("Score", "N/A")
        feedback = extracted.get("Feedback", "N/A")
        return score, feedback
      
    except Exception as e:
          print(f"An error occurred in Extract: {e}")
          return "N/A","N/A" 