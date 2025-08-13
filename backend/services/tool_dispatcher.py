"""Tool dispatcher combining CRUD + aggregation for OpenAI tool calling.

Purpose: Provide a single execute() surface so the chat layer only needs the
function name + JSON args (mirrors the OpenAI tool call contract) without
embedding Jira specifics in the conversation layer.
"""
from typing import Dict, Tuple, Any
from ..jira_utils import aggregate_issues, JiraManager
from . import jira_crud
from ..config import JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD

_jira_manager = None

def jira_manager():
    """Lazy singleton JiraManager."""
    global _jira_manager
    if _jira_manager is None:
        _jira_manager = JiraManager(JIRA_BASE_URL, JIRA_USERNAME, JIRA_PASSWORD)
    return _jira_manager

def execute(function_name: str, args: Dict) -> Tuple[Any, str]:
    """Execute a tool function by name.

    Returns: (result, error) where exactly one is non-null.
    Unknown function names return (None, error_msg).
    Catches all exceptions to prevent bubbling into the chat flow.
    """
    try:
        # Dispatch mapping from function name to CRUD or aggregation operation
        if function_name == 'get_issues':
            return jira_crud.execute_jql_search(**args)
        if function_name == 'get_projects':
            return jira_crud.get_all_projects()
        if function_name == 'get_issue_types':
            return jira_crud.get_issue_types(**args)
        if function_name == 'get_worklogs':
            args['username'] = JIRA_USERNAME
            return jira_crud.get_worklogs(**args)
        if function_name == 'create_worklog':
            return jira_crud.create_worklog(**args)
        if function_name == 'update_worklog':
            return jira_crud.update_worklog(**args)
        if function_name == 'delete_worklog':
            return jira_crud.delete_worklog(**args)
        if function_name == 'manage_issue':
            action = args.get('action'); details = args.get('details', {})
            # Manage issue can create, update, or delete based on action
            if action == 'create': return jira_crud.create_issue(details)
            if action == 'update':
                issue_key = details.pop('issue_key', None)
                return jira_crud.update_issue(issue_key, details)
            if action == 'delete': return jira_crud.delete_issue(details.get('issue_key',))
        if function_name == 'aggregate_issues':
            return aggregate_issues(jira_manager(), **args)
        return None, f"Fungsi '{function_name}' tidak ditemukan."
    except Exception as e:
        # Handle and log the exception, returning an error message
        return None, f"Exception saat eksekusi tool: {e}"
