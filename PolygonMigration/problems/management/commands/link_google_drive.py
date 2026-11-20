import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from problems.gdrive_storage import DRIVE_SCOPE, credentials_path, token_path


class Command(BaseCommand):
    help = "Sign in to Google Drive and save a folder for test-case uploads."

    def handle(self, *args, **options):
        client_file = credentials_path()
        if not client_file or not os.path.exists(client_file):
            raise CommandError(
                "Missing the Google OAuth client file.\n"
                "1. Open https://console.cloud.google.com/apis/library/drive.googleapis.com and enable the Google Drive API.\n"
                "2. Open https://console.cloud.google.com/apis/credentials\n"
                "3. Create credentials, choose OAuth client ID, and choose Desktop app.\n"
                f"4. Download the JSON and save it as {client_file}\n"
                "5. Run this command again. The browser will ask you to allow access."
            )

        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(client_file, [DRIVE_SCOPE])
        creds = flow.run_local_server(port=8765, access_type="offline", prompt="consent")
        destination = token_path()
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf-8") as token_handle:
            token_handle.write(creds.to_json())
        os.chmod(destination, 0o600)

        from googleapiclient.discovery import build

        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        folder_id = settings.GOOGLE_DRIVE_FOLDER_ID or _ensure_root_folder(service)
        _set_env_values({
            "STORAGE_PROVIDER": "gdrive",
            "GOOGLE_DRIVE_CREDENTIALS_FILE": settings.GOOGLE_DRIVE_CREDENTIALS_FILE,
            "GOOGLE_DRIVE_TOKEN_FILE": settings.GOOGLE_DRIVE_TOKEN_FILE,
            "GOOGLE_DRIVE_FOLDER_ID": folder_id,
        })
        self.stdout.write(self.style.SUCCESS(
            "Google Drive is linked. Test cases will upload under "
            f"https://drive.google.com/drive/folders/{folder_id}"
        ))


def _ensure_root_folder(service):
    query = (
        "name = 'Polygon test cases' and "
        "mimeType = 'application/vnd.google-apps.folder' and "
        "'root' in parents and trashed = false"
    )
    found = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
    files = found.get("files", [])
    if files:
        return files[0]["id"]
    created = service.files().create(
        body={
            "name": "Polygon test cases",
            "mimeType": "application/vnd.google-apps.folder",
        },
        fields="id",
    ).execute()
    return created["id"]


def _set_env_values(updates):
    env_path = os.path.join(settings.BASE_DIR, ".env")
    with open(env_path, encoding="utf-8") as env_file:
        lines = env_file.read().splitlines()
    remaining = dict(updates)
    written = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else None
        if key in remaining:
            written.append(f"{key}={remaining.pop(key)}")
        else:
            written.append(line)
    for key, value in remaining.items():
        written.append(f"{key}={value}")
    with open(env_path, "w", encoding="utf-8") as env_file:
        env_file.write("\n".join(written) + "\n")
