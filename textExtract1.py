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
  "max_output_tokens": 8192,
  "response_schema": content.Schema(
    type = content.Type.OBJECT,
    enum = [],
    required = ["Name", "Student Number","Section", "Question", "Answer"],
    properties = {
      "Name": content.Schema(
        type = content.Type.STRING,
      ),
      "Section": content.Schema(
        type = content.Type.STRING,
      ),
      "Student Number": content.Schema(
        type = content.Type.INTEGER,
      ),
      "Question": content.Schema(
        type = content.Type.STRING,
      ),
      "Answer": content.Schema(
        type = content.Type.STRING,
      ),
    },
  ),
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-2.0-flash",
  generation_config=generation_config,
  system_instruction="extract the Name, Section, Student Number, Question, and Answer from the image file. Return N/A if none. The answer is in English so match OCR with words in the English dictionary as possible. Section is strictly in the format [year level i.e., 1, 2, 3, 4][Program Code i.e., CPE, IE, BEED, ECE, etc.]-[Section letter i.e., A, B, C,...] ex: 3CPE-A, 4IE-B, 1SEED-C. Student number is any 7 digit combination. NAME IS PROPERLY LABELED AT THE TOPMOST BOX. SECTION IS BELOW THAT. DO NOT GET IT MIXED UP.",
)

def extract1(picture):
    try:
        prompt = "extract"
        picture1 = Image.open(picture)

        response = model.generate_content([prompt, picture1])
        extracted = json.loads(response.text)

        # Extract fields with fallback to "N/A"
        student_no = extracted.get("Student Number", "N/A")
        name = extracted.get("Name", "N/A")
        section = extracted.get("Section", "N/A")
        answer = extracted.get("Answer", "N/A")
        question = extracted.get("Question", "N/A")

        return student_no, name, section, answer, question

    except Exception as e:
        print(f"[ERROR] Extract failed for {picture}: {e}")
        return "N/A", "N/A", "N/A", "N/A", "N/A"
