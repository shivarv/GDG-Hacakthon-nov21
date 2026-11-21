"""One-time Gmail sign-in for the helpdesk.

1. In Google Cloud console: enable the Gmail API, configure the OAuth consent screen,
   create an OAuth client of type "Desktop app", and download its JSON to
   backend/.data/gmail_credentials.json
2. Run from the backend folder:   python scripts/gmail_auth.py
3. Sign in as the helpdesk Gmail account (the SUPPORT_FROM_ADDRESS) in the browser window that opens.

The resulting token is saved to backend/.data/gmail_token.json (gitignored).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.gmail.client import SCOPES  # noqa: E402

settings = get_settings()
credentials_file = Path(settings.gmail_credentials_file)
if not credentials_file.exists():
    sys.exit(f"Missing {credentials_file}\nDownload your OAuth client JSON (Desktop app) from Google Cloud and save it there.")

flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
token_file = Path(settings.gmail_token_file)
token_file.parent.mkdir(parents=True, exist_ok=True)
token_file.write_text(creds.to_json())

print(f"\nGmail connected (send-only). Token saved to {token_file}")
print("SUPPORT_FROM_ADDRESS in backend/.env must be the Gmail account you just signed in with.")
