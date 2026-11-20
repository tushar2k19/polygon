import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
FOLDER_MIME = "application/vnd.google-apps.folder"


def drive_path(path):
    """Resolve a path from .env against the Django project directory."""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.join(settings.BASE_DIR, path)


def credentials_path():
    return drive_path(settings.GOOGLE_DRIVE_CREDENTIALS_FILE)


def token_path():
    return drive_path(settings.GOOGLE_DRIVE_TOKEN_FILE)


class GoogleDriveStorage:
    """
    Stores test files in the signed-in user's Google Drive.

    Layout under the configured folder:
        test_cases/{problem_id}/{test_number}
        test_cases/{problem_id}/{test_number}.a
    """

    def __init__(self):
        self.service = build_drive_service()
        self.root_id = settings.GOOGLE_DRIVE_FOLDER_ID
        if not self.root_id:
            raise RuntimeError(
                "GOOGLE_DRIVE_FOLDER_ID is empty. Run: python manage.py link_google_drive"
            )

    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        problem_folder = self._problem_folder(problem_id)
        prefix = f"{int(test_number):02d}"
        self._put_text(problem_folder, prefix, input_data)
        self._put_text(problem_folder, f"{prefix}.a", output_data)
        logger.info("Uploaded test %s for problem %s to Google Drive", prefix, problem_id)

    def delete_problem_tests(self, problem_id):
        tests_folder = self._find("test_cases", self.root_id, FOLDER_MIME)
        if not tests_folder:
            return
        problem_folder = self._find(str(problem_id), tests_folder, FOLDER_MIME)
        if not problem_folder:
            return
        for item in self._list_children(problem_folder):
            self.service.files().delete(fileId=item["id"]).execute()
            logger.info("Deleted Drive file %s", item.get("name"))

    def problem_folder_url(self, problem_id):
        folder_id = self._problem_folder(problem_id)
        return f"https://drive.google.com/drive/folders/{folder_id}"

    def read_text(self, problem_id, filename):
        folder_id = self._problem_folder(problem_id)
        file_id = self._find(filename, folder_id)
        if not file_id:
            raise FileNotFoundError(filename)
        data = self.service.files().get_media(fileId=file_id).execute()
        return data.decode("utf-8")

    def _problem_folder(self, problem_id):
        tests_folder = self._ensure_folder("test_cases", self.root_id)
        return self._ensure_folder(str(problem_id), tests_folder)

    def _put_text(self, parent_id, name, text):
        payload = text.encode("utf-8")
        existing = self._find(name, parent_id)
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(payload, mimetype="text/plain", resumable=False)
        if existing:
            self.service.files().update(fileId=existing, media_body=media).execute()
            return
        self.service.files().create(
            body={"name": name, "parents": [parent_id]},
            media_body=media,
            fields="id",
        ).execute()

    def _ensure_folder(self, name, parent_id):
        found = self._find(name, parent_id, FOLDER_MIME)
        if found:
            return found
        created = self.service.files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
            fields="id",
        ).execute()
        return created["id"]

    def _find(self, name, parent_id, mime_type=None):
        safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{safe_name}' and '{parent_id}' in parents and trashed = false"
        )
        if mime_type:
            query += f" and mimeType = '{mime_type}'"
        response = self.service.files().list(
            q=query,
            fields="files(id,name)",
            pageSize=1,
        ).execute()
        files = response.get("files", [])
        return files[0]["id"] if files else None

    def _list_children(self, parent_id):
        children = []
        page_token = None
        while True:
            response = self.service.files().list(
                q=f"'{parent_id}' in parents and trashed = false",
                fields="nextPageToken, files(id,name)",
                pageSize=100,
                pageToken=page_token,
            ).execute()
            children.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return children


def build_drive_service():
    """Build an authorized Drive client from the saved OAuth token."""
    token_file = token_path()
    if not token_file or not os.path.exists(token_file):
        raise RuntimeError(
            "Google Drive is not linked. Run: python manage.py link_google_drive"
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(token_file, [DRIVE_SCOPE])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w", encoding="utf-8") as token_handle:
            token_handle.write(creds.to_json())
    if not creds.valid:
        raise RuntimeError(
            "Google Drive login expired. Run: python manage.py link_google_drive"
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)
