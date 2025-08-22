"""Jira CRUD & worklog helper functions (now using session credentials)."""

from datetime import datetime, timedelta
from ..utils.session_jira import get_session_credentials
from typing import Dict, Any
import base64
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

try:
    from jira import JIRA  # type: ignore
except ImportError:
    JIRA = None


def jira_client():
    base_url, username, password = get_session_credentials()
    if not JIRA or not all([base_url, username, password]):
        return None
    try:
        return JIRA(server=base_url, basic_auth=(username, password))
    except Exception:
        return None


def execute_jql_search(jql_query: str, max_results: int = 50):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        issues = client.search_issues(jql_query, maxResults=max_results)
        out = []
        for issue in issues:
            f = issue.fields
            out.append(
                {
                    "key": issue.key,
                    "fields": {
                        "summary": f.summary,
                        "status": {"name": f.status.name if f.status else None},
                        "assignee": {
                            "displayName": (
                                f.assignee.displayName if f.assignee else None
                            )
                        },
                        "priority": {"name": f.priority.name if f.priority else None},
                        "created": f.created,
                        "updated": f.updated,
                        "dueDate": f.duedate,
                        "reporter": {"displayName": f.reporter.displayName},
                        "issuetype": {"name": f.issuetype.name}
                    },
                }
            )
        return out, None
    except Exception as e:
        return None, f"Error eksekusi JQL: {e}"


def get_all_projects():
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        # Get current user
        current_user = client.current_user()
        username = current_user if isinstance(current_user, str) else current_user.name
        
        # Search for open issues where the current user is involved (assignee, reporter, or has worked on)
        jql = f"(assignee = '{username}' OR reporter = '{username}' OR worklogAuthor = '{username}') AND resolution = Unresolved"
        issues = client.search_issues(jql, maxResults=1000, fields="project")
        
        # Extract unique projects from the issues
        project_keys = set()
        for issue in issues:
            project_keys.add(issue.fields.project.key)
        
        # Get project details for the projects the user has issues in
        user_projects = []
        for project_key in project_keys:
            try:
                project = client.project(project_key)
                user_projects.append({"key": project.key, "name": project.name})
            except Exception:
                # Skip projects that can't be accessed
                continue
        
        return user_projects, None
    except Exception as e:
        return None, f"Error mengambil projek: {e}"


def get_issue_types(project_key=None):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        if project_key:
            meta = client.project(project_key)
            return [{"name": t.name} for t in meta.issueTypes], None
        return [{"name": t.name} for t in client.issue_types()], None
    except Exception as e:
        return None, f"Error issue types: {e}"


def get_worklogs(from_date: str, to_date: str, username: str):
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    try:
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{from_date}' AND worklogDate <= '{to_date}'"
        issues = client.search_issues(jql, maxResults=200)
        rows = []
        for issue in issues:
            try:
                for w in client.worklogs(issue.key):
                    started = getattr(w, "started", "")
                    if started and from_date <= started[:10] <= to_date:
                        author_name = getattr(
                            getattr(w, "author", None), "name", ""
                        ) or getattr(getattr(w, "author", None), "displayName", "")
                        if author_name == username:
                            rows.append(
                                {
                                    "id": w.id,
                                    "issueKey": issue.key,
                                    "issueSummary": issue.fields.summary,
                                    "comment": getattr(w, "comment", ""),
                                    "timeSpent": getattr(w, "timeSpent", ""),
                                    "started": started,
                                    "author": author_name,
                                }
                            )
            except Exception:
                continue
        return rows, None
    except Exception as e:
        return None, f"Error mengambil worklog: {e}"


def create_worklog(issue_key, time_spent_hours, description):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        wl = client.add_worklog(
            issue=issue_key,
            timeSpentSeconds=int(float(time_spent_hours) * 3600),
            comment=description,
            started=datetime.now(),
        )
        return {
            "id": wl.id,
            "issueKey": issue_key,
            "timeSpent": wl.timeSpent,
            "comment": wl.comment,
            "started": wl.started,
        }, None
    except Exception as e:
        return None, f"Gagal membuat worklog: {e}"


def update_worklog(issue_key, worklog_id, time_spent_hours=None, description=None):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        data = {}
        if time_spent_hours is not None:
            data["timeSpentSeconds"] = int(float(time_spent_hours) * 3600)
        if description is not None:
            data["comment"] = description
        if not data:
            return None, "Tidak ada data untuk diupdate."
        wl = client.worklog(issue_key, worklog_id)
        wl.update(**data)
        return {"id": wl.id, "issueKey": issue_key}, None
    except Exception as e:
        return None, f"Gagal update worklog: {e}"


def delete_worklog(issue_key, worklog_id):
    client = jira_client()
    if not client:
        return False, "Jira client tidak terinisialisasi."
    try:
        wl = client.worklog(issue_key, worklog_id)
        wl.delete()
        return True, None
    except Exception as e:
        return False, f"Gagal hapus worklog: {e}"


def create_issue(details: Dict[str, Any]):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        if not details.get("summary") or not details.get("project_key"):
            return None, "Summary dan Project key diperlukan."
        issue_data = {
            "project": {"key": details["project_key"]},
            "summary": details["summary"],
            "issuetype": {"name": details.get("issuetype_name", "Task")},
        }
        if details.get("description"):
            issue_data["description"] = details["description"]
        if details.get("acceptance_criteria"):
            issue_data["customfield_10561"] = details["acceptance_criteria"]
        if details.get("priority_name"):
            issue_data["priority"] = {"name": details["priority_name"]}
        if details.get("assignee_name"):
            issue_data["assignee"] = {"name": details["assignee_name"]}
        if details.get("duedate"):
            issue_data["duedate"] = details["duedate"]
        issue = client.create_issue(fields=issue_data)
        return {"key": issue.key}, None
    except Exception as e:
        return None, f"Gagal membuat issue: {e}"


def update_issue(issue_key, updates: Dict[str, Any]):
    client = jira_client()
    if not client:
        return None, "Jira client tidak terinisialisasi."
    try:
        field_updates = {}
        for key, value in updates.items():
            if key == "assignee_name":
                # Map pseudo field 'assignee_name' to real Jira 'assignee'
                if value is None:
                    field_updates["assignee"] = None  # Unassign
                else:
                    field_updates["assignee"] = {"name": value}
            elif key == "priority_name":
                field_updates["priority"] = {"name": value}
            elif key == "issuetype_name":
                field_updates["issuetype"] = {"name": value}
            else:
                field_updates[key] = value

        issue = client.issue(issue_key)
        issue.update(fields=field_updates)
        return {"key": issue_key}, None
    except Exception as e:
        return None, f"Gagal update issue: {e}"


def delete_issue(issue_key):
    client = jira_client()
    if not client:
        return False, "Jira client tidak terinisialisasi."
    try:
        client.issue(issue_key).delete()
        return True, None
    except Exception as e:
        return False, f"Gagal hapus issue: {e}"

def export_worklog_data(start_date: str, end_date: str, username: str, full_name: str):
    """Export worklog data in table format with PDF download option."""
    client = jira_client()
    if not client:
        return None, "Jira client tidak tersedia"
    
    try:
        start_dt, end_dt = datetime.strptime(start_date, "%Y-%m-%d"), datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return _create_error_response(start_date, username, full_name), None
        
        # Get worklogs
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{start_date}' AND worklogDate <= '{end_date}'"
        issues = client.search_issues(jql, maxResults=500)
        
        worklog_data = []
        project_cache = {}
        
        for issue in issues:
            try:
                if issue.fields.project.key not in project_cache:
                    project_cache[issue.fields.project.key] = issue.fields.project.name
                
                for worklog in client.worklogs(issue.key):
                    if _is_valid_worklog(worklog, start_date, end_date, username):
                        worklog_data.append(_extract_worklog_data(worklog, issue, project_cache))
            except Exception:
                continue
        
        # Generate tables
        table_rows = _generate_table_rows(worklog_data, start_dt, end_dt, username, full_name)
        markdown_table = _build_markdown_table(table_rows, start_dt, end_dt, full_name, worklog_data, client)
        
        # Generate PDF
        pdf_buffer = _generate_pdf_table(table_rows, start_dt, end_dt, full_name, worklog_data)
        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        download_link = f"data:application/pdf;base64,{pdf_b64}"
        
        return {
            "table": markdown_table,
            "download_link": download_link,
            "filename": f"timesheet_{username}_{start_date}_{end_date}.pdf"
        }, None
        
    except Exception as e:
        return None, f"Error exporting worklog data: {e}"

def _is_valid_worklog(worklog, start_date, end_date, username):
    started = getattr(worklog, "started", "")
    if not started or not (start_date <= started[:10] <= end_date):
        return False
    
    author = getattr(worklog, "author", None)
    if not author:
        return False
    
    author_name = getattr(author, "name", "") or getattr(author, "displayName", "")
    return author_name == username

def _extract_worklog_data(worklog, issue, project_cache):
    hours_float = getattr(worklog, "timeSpentSeconds", 0) / 3600
    hours = int(hours_float) if hours_float == int(hours_float) else round(hours_float, 1)
    description = getattr(worklog, "comment", "") or "—"
    
    activity_type = getattr(worklog, "activityType", None)
    activity_type = getattr(activity_type, "name", "Development") if activity_type else "Development"
    
    return {
        "issue_key": issue.key,
        "description": description,
        "hours": hours,
        "work_date": getattr(worklog, "started", "")[:10],
        "project_name": project_cache[issue.fields.project.key],
        "activity_type": activity_type
    }

def _generate_table_rows(worklog_data, start_dt, end_dt, username, full_name):
    table_rows = []
    current_date = start_dt
    day_no = 1
    
    while current_date <= end_dt:
        date_str = current_date.strftime("%Y-%m-%d")
        day_worklogs = [w for w in worklog_data if w["work_date"] == date_str]
        
        if day_worklogs:
            for i, worklog in enumerate(day_worklogs):
                row_day_no = day_no if i == 0 else ""
                table_rows.append([
                    str(row_day_no), worklog['issue_key'], worklog['description'][:50] + "..." if len(worklog['description']) > 50 else worklog['description'],
                    str(worklog['hours']), "1", date_str, username, full_name, 
                    worklog['project_name'], worklog['activity_type']
                ])
            day_no += 1  # Only increment when there are worklogs
        else:
            table_rows.append(["", "", "", "", "", date_str, "", "", "", ""])
        
        current_date += timedelta(days=1)
    
    return table_rows

def _build_markdown_table(table_rows, start_dt, end_dt, full_name, worklog_data, client):
    month_start = start_dt.strftime("%m/%d")
    month_end = end_dt.strftime("%m/%d") 
    period_year = start_dt.strftime("%Y")
    month_range = f"{start_dt.strftime('%B %d')} - {end_dt.strftime('%B %d')}"
    
    project_name = worklog_data[0]['project_name'] if worklog_data else ""
    
    timesheet_header = f"""**Consultant Timesheet - {month_start}/{month_end} {period_year}**

Name: {full_name}\n
Role: \n
Project: {project_name}\n
Month: {month_range}\n
Year: {period_year}\n\n
"""
    
    header = "| No | Issue Key | Issue Summary | Hours | MD | Work Date | Username | Full Name | Project Name | Activities Type |"
    separator = "|---|---|---|---|---|---|---|---|---|---|"
    
    markdown_rows = []
    for row in table_rows:
        markdown_rows.append("| " + " | ".join(row) + " |")
    
    return timesheet_header + header + "\n" + separator + "\n" + "\n".join(markdown_rows)

def _generate_pdf_table(table_rows, start_dt, end_dt, full_name, worklog_data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=40, bottomMargin=20)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=12,
        spaceAfter=8,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#2c3e50')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=6,
        textColor=colors.HexColor('#34495e')
    )
    
    # Cell text style for wrapping
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=6,
        textColor=colors.HexColor('#2c3e50'),
        wordWrap='LTR',
        alignment=0,  # Left alignment
        leftIndent=1,
        rightIndent=1,
        spaceAfter=1,
        spaceBefore=1
    )
    
    # Content
    story = []
    
    # Title
    month_start = start_dt.strftime("%m/%d")
    month_end = end_dt.strftime("%m/%d") 
    period_year = start_dt.strftime("%Y")
    month_range = f"{start_dt.strftime('%B %d')} - {end_dt.strftime('%B %d')}"
    project_name = worklog_data[0]['project_name'] if worklog_data else ""
    
    story.append(Paragraph(f"Consultant Timesheet - {month_start}/{month_end} {period_year}", title_style))
    story.append(Spacer(1, 8))
    
    # Header info
    story.append(Paragraph(f"<b>Name:</b> {full_name}", subtitle_style))
    story.append(Paragraph(f"<b>Role:</b> ", subtitle_style))
    story.append(Paragraph(f"<b>Project:</b> {project_name}", subtitle_style))
    story.append(Paragraph(f"<b>Period:</b> {month_range}, {period_year}", subtitle_style))
    story.append(Spacer(1, 12))
    
    # Table headers
    headers = ['No', 'Issue Key', 'Issue Summary', 'Hours', 'MD', 'Work Date', 'Username', 'Full Name', 'Project', 'Activity Type']
    
    # Convert headers to Paragraph objects for consistent styling
    header_paragraphs = [Paragraph(str(header), cell_style) for header in headers]
    
    # Convert table data to Paragraph objects to enable text wrapping
    processed_rows = []
    for row in table_rows:
        processed_row = []
        for i, cell in enumerate(row):
            cell_text = str(cell) if cell is not None else ""
            # Use center alignment for specific columns (No, Hours, MD)
            if i in [0, 3, 4]:  # No, Hours, MD columns
                centered_style = ParagraphStyle(
                    'CenteredCellText',
                    parent=cell_style,
                    alignment=1  # Center alignment
                )
                processed_row.append(Paragraph(cell_text, centered_style))
            else:
                processed_row.append(Paragraph(cell_text, cell_style))
        processed_rows.append(processed_row)
    
    # Combine headers and data
    data = [header_paragraphs] + processed_rows
    
    # Create table with adjusted column widths for portrait
    table = Table(data, colWidths=[0.3*inch, 0.6*inch, 1.8*inch, 0.4*inch, 0.3*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.7*inch])
    
    # Base table style
    table_style_commands = [
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Data rows - basic styling
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2c3e50')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        
        # Base grid and borders - only vertical lines and header border
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),  # Vertical lines
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2980b9')),  # Header bottom border
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),  # Outer border
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        
        # Enable text wrapping by allowing variable row heights
        ('ROWSPLITMODE', (0, 0), (-1, -1), 'SPAN'),
    ]
    
    # Group rows by date and apply same background color + remove horizontal borders
    if len(table_rows) > 0:
        # Assuming Work Date is at index 5 (6th column)
        work_date_col = 5
        colors_list = [colors.HexColor('#f8f9fa'), colors.HexColor('#e9ecef')]
        current_color_index = 0
        
        # Track date groups and apply colors
        i = 0
        while i < len(table_rows):
            current_date = table_rows[i][work_date_col] if len(table_rows[i]) > work_date_col else None
            
            # Find all consecutive rows with same date
            group_start = i
            group_end = i
            
            while group_end < len(table_rows) - 1:
                next_date = table_rows[group_end + 1][work_date_col] if len(table_rows[group_end + 1]) > work_date_col else None
                if current_date == next_date and current_date is not None:
                    group_end += 1
                else:
                    break
            
            # Apply same background color to entire date group
            current_color = colors_list[current_color_index % 2]
            table_style_commands.append(
                ('BACKGROUND', (0, group_start + 1), (-1, group_end + 1), current_color)
            )
            
            # Remove horizontal borders within the group
            for row_idx in range(group_start, group_end):
                table_style_commands.append(
                    ('LINEBELOW', (0, row_idx + 1), (-1, row_idx + 1), 0, None)
                )
            
            current_color_index += 1
            i = group_end + 1
    
    # Apply the style
    table.setStyle(TableStyle(table_style_commands))
    
    story.append(table)
    doc.build(story)
    
    buffer.seek(0)
    return buffer

def _create_error_response(start_date, username, full_name):
    return {
        "table": f"| No | Issue Key | Issue Summary | Hours | MD | Work Date | Username | Full Name | Project Name | Activities Type |\n|---|---|---|---|---|---|---|---|---|---|\n| 1 |  | Invalid date range | 0 | 1 | {start_date} | {username} | {full_name} |  |  |"
    }