import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set and non-empty for secure session management.")

JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_PASSWORD = os.getenv('JIRA_PASSWORD')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "20"))

CURRENT_DATE = datetime.now().strftime('%Y-%m-%d')
CURRENT_TIME = datetime.now().strftime('%H:%M:%S')
