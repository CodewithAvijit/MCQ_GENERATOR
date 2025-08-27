import os
import re
import json
import PyPDF2
import traceback
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain, SequentialChain
from langchain.callbacks import get_openai_callback

# Load environment variables
load_dotenv()
key = os.getenv("GEMINI_KEY")

# FastAPI app
app = FastAPI(title="MCQ Generator API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Initialize Google GenAI client
client = ChatGoogleGenerativeAI(
    model="gemma-3-12b-it",
    google_api_key=key,
    temperature=0.5
)

# Response format
response_json = {
    "1": {
        "mcq": "multiple choice question",
        "option": {
            "a": "choice here",
            "b": "choice here",
            "c": "choice here",
            "d": "choice here",
        },
        "correct": "correct answer",
    }
}

# Prompt for quiz generation
TEMPLATE = """
You are an expert MCQ generator.  
Create {number} MCQs from {text} for {subject} students in a {tone} tone.  

Rules:
- Output ONLY valid JSON.  
- Do NOT add ``` or any markdown formatting.  
- Do NOT write the word 'json'.  
- Return pure JSON object only.  
- It must start with {{ and end with }}.  

Here is the RESPONSE_JSON format you must strictly follow:  
{response_json}
"""

quiz_generation = PromptTemplate(
    input_variables=["text", "number", "subject", "tone", "response_json"],
    template=TEMPLATE
)
quiz_chain = LLMChain(llm=client, prompt=quiz_generation, output_key="quiz", verbose=True)

# Prompt for quiz evaluation
template2 = """
You are an expert English grammarian and writer who evaluates the quiz for {subject} students.
Fix and polish the MCQs below:  
{quiz}  

Rules:  
- Output ONLY valid JSON.  
- No markdown or ```json.  
- Must be suitable for json.loads.
"""
quiz_evalute = PromptTemplate(
    input_variables=['subject', 'quiz'],
    template=template2
)
review_chain = LLMChain(llm=client, prompt=quiz_evalute, output_key="review", verbose=True)

# Final chain
final_chain = SequentialChain(
    chains=[quiz_chain, review_chain],
    input_variables=["text", "number", "subject", "tone", "response_json"],
    output_variables=['quiz', "review"],
    verbose=True
)

# PDF to text function
def pdf_to_text(pdf_file) -> str:
    text = ""
    reader = PyPDF2.PdfReader(pdf_file)
    for page in reader.pages:
        text += page.extract_text() or ""
        text += "\n"
    return text

def clean_json_output(output: str):
    """Remove markdown wrappers like ```json ... ```"""
    output = re.sub(r"```json|```", "", output).strip()
    return output

@app.post("/generate_mcq/")
async def generate_mcq(
    file: UploadFile,
    number: int = Form(...),
    subject: str = Form(...),
    tone: str = Form(...)
):
    """
    Upload a PDF and generate MCQs.
    """
    try:
        # Convert PDF to text
        pdf_text = pdf_to_text(file.file)

        # Run chain
        with get_openai_callback() as cb:
            response = final_chain.invoke({
                "text": pdf_text,
                "number": number,
                "subject": subject,
                "tone": tone,
                "response_json": json.dumps(response_json)
            })

        # Clean & parse outputs
        quiz_json = json.loads(clean_json_output(response["quiz"]))
        review_json = json.loads(clean_json_output(response["review"]))

        return JSONResponse(content={
            "quiz": quiz_json,
            "review": review_json
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)
