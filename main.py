import os.path
from flask import Flask, render_template, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
    """Handles authentication and returns the Gmail API service instance."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    credentials_path = os.path.join(base_dir, 'credentials.json')

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def process_received_emails(search_keyword, force_star):
    """Core logic to scan and star emails based on criteria."""
    service = get_gmail_service()
    response = service.users().messages().list(userId='me', q=search_keyword, maxResults=100).execute()
    messages = response.get('messages', [])

    logs = []
    if not messages:
        return ["❌ No matching emails found."]

    for msg in messages:
        msg_details = service.users().messages().get(userId='me', id=msg['id']).execute()
        labels = msg_details.get('labelIds', [])
        snippet = msg_details.get('snippet', '')[:60]

        is_unread = 'UNREAD' in labels
        is_already_starred = 'STARRED' in labels

        log_entry = f"✉️ \"{snippet}...\""
        
        if is_unread or force_star:
            if not is_already_starred:
                service.users().messages().batchModify(
                    userId='me', body={'ids': [msg['id']], 'addLabelIds': ['STARRED']}
                ).execute()
                log_entry += " ➡️ ⭐ ACTION: Starred!"
            else:
                log_entry += " ➡️ ℹ️ STATUS: Already starred. Skipped."
        else:
            log_entry += " ➡️ ⏭️ ACTION: Ignored (Opened/Read)."
        
        logs.append(log_entry)
    
    return logs

@app.route('/')
def home():
    """Renders the frontend dashboard."""
    return render_template('index.html')

@app.route('/run-automation', methods=['POST'])
def run_automation():
    """API endpoint called by the UI buttons."""
    data = request.json
    target_email = data.get('email')
    force_star_flag = data.get('force_star', False)
    
    if not target_email:
        return jsonify({'error': 'Please provide a sender email address.'}), 400
    
    try:
        execution_logs = process_received_emails(target_email, force_star_flag)
        return jsonify({'logs': execution_logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Start the web server locally on port 5000
    app.run(debug=True, port=5000)