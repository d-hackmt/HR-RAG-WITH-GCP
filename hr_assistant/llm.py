"""12 · llm — connect to the model.

One place, one model: get_llm() returns a LangChain chat model that calls
Vertex AI Gemini directly (config.LLM_MODEL_NAME). Auth is Application
Default Credentials — `gcloud auth application-default login` locally, the
service account on Cloud Run.

Deliberately tiny at this stage. Fallback routing (a second provider if
Vertex errors) is added in a later stage.
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from hr_assistant import config


def get_llm():
    """The app's chat model — Vertex AI Gemini, temperature 0."""
    return ChatGoogleGenerativeAI(
        model=config.LLM_MODEL_NAME,
        vertexai=True,
        project=config.PROJECT_ID,
        location=config.LOCATION,
        temperature=0,
    )
