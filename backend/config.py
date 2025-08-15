import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set and non-empty for secure session management."
    )

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_PASSWORD = os.getenv("JIRA_PASSWORD")

# Azure OpenAI Configuration (Active)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

# Regular OpenAI Configuration (Commented out - can be enabled if needed)
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")



MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
CURRENT_TIME = datetime.now().strftime("%H:%M:%S")
