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
        if function_name == "get_issue_details":
            return jira_crud.get_issue_details(**args)
        if function_name == "get_issues":
            return jira_crud.execute_jql_search(**args)
        if function_name == "get_projects":
            return jira_crud.get_all_projects()
        if function_name == "get_issue_types":
            return jira_crud.get_issue_types(**args)
        if function_name == "get_issue_worklogs":
            return jira_crud.get_issue_worklogs(**args)
        if function_name == "get_worklogs":
            from ..utils.session_jira import get_session_credentials

            _, session_username, _ = get_session_credentials()
            args["username"] = session_username or args.get("username", "unknown")
            return jira_crud.get_worklogs(**args)
        if function_name == "create_worklog":
            return jira_crud.create_worklog(**args)
        if function_name == "update_worklog":
            return jira_crud.update_worklog(**args)
        if function_name == "delete_worklog":
            return jira_crud.delete_worklog(**args)
        if function_name == "manage_issue":
            action = args.get("action")
            details = args.get("details", {})
            # Manage issue can create, update, or delete based on action
            if action == "create":
                return jira_crud.create_issue(details)
            if action == "update":
                issue_key = details.pop("issue_key", None)
                return jira_crud.update_issue(issue_key, details)
            if action == "delete":
                return jira_crud.delete_issue(
                    details.get(
                        "issue_key",
                    )
                )
        if function_name == "aggregate_issues":
            return aggregate_issues(jira_manager(), **args)
        if function_name == "search_users":
            partial_name = args.get("partial_name", "")
            max_results = args.get("max_results", 50)
            project = args.get("project")  # Can be None
            users = jira_manager().fuzzy_search_users(partial_name, project, max_results)
            return users, None
        if function_name == "export_worklog_data":
            from datetime import datetime, timedelta
            from ..utils.session_jira import get_session_credentials
            from flask import session
            
            _, session_username, _ = get_session_credentials()
            full_name = session.get("jira_display_name", session_username or "Unknown User")
            
            # Default to last 30 days if dates not provided
            end_date = args.get("end_date")
            start_date = args.get("start_date")
            
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")
            
            if not start_date:
                start_datetime = datetime.now() - timedelta(days=30)
                start_date = start_datetime.strftime("%Y-%m-%d")
            
            return jira_crud.export_worklog_data(
                start_date=start_date,
                end_date=end_date,
                username=session_username or "unknown",
                full_name=full_name
            )
        if function_name == "get_issue_transitions":
            return jira_crud.get_issue_transitions(**args)
        if function_name == "update_issue_status":
            issue_key = args.get("issue_key")
            target_status = args.get("target_status")
            return jira_crud.update_issue_status(issue_key, target_status)
        return None, f"Fungsi '{function_name}' tidak ditemukan."
    except Exception as e:
        # Handle and log the exception, returning an error message
        return None, f"Exception saat eksekusi tool: {e}"
