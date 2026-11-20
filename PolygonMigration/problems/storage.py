import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class TestCaseStorage:
    """Stores full test-case files for one database problem."""

    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        raise NotImplementedError

    def delete_problem_tests(self, problem_id):
        raise NotImplementedError

    def problem_folder_url(self, problem_id):
        return ""


def get_test_case_storage():
    """Return the storage backend selected by STORAGE_PROVIDER."""
    provider = getattr(settings, "STORAGE_PROVIDER", "azure")
    if provider == "gdrive":
        from problems.gdrive_storage import GoogleDriveStorage
        return GoogleDriveStorage()
    if provider == "azure":
        from problems.AzureTestcase import AzureBlobManager
        return AzureTestCaseStorage(AzureBlobManager(
            account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            username=settings.AZURE_USERNAME,
            password=settings.AZURE_PASSWORD,
        ), settings.AZURE_CONTAINER_NAME)
    raise ValueError(
        f"STORAGE_PROVIDER={provider!r} is not implemented. Use 'gdrive' or 'azure'."
    )


class AzureTestCaseStorage(TestCaseStorage):
    """Adapter so the existing Azure uploader matches TestCaseStorage."""

    def __init__(self, manager, container_name):
        self.manager = manager
        self.container_name = container_name

    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        self.manager.upload_test_case(
            self.container_name, problem_id, test_number, input_data, output_data
        )

    def delete_problem_tests(self, problem_id):
        self.manager.empty_blob(self.container_name, problem_id)


def upload_problem_tests(polygon_api, polygon_id, db_problem_id, testset="tests"):
    """
    Upload every test case that has both input and output.

    Files are named test_cases/{db_problem_id}/{test_number}
    and test_cases/{db_problem_id}/{test_number}.a.
    Existing files for that problem are removed first.
    """
    test_cases = polygon_api.get_test_cases_from_redis(polygon_id)
    if test_cases is None:
        logger.warning("Test cases not found in Redis, fetching from Polygon")
        test_cases = polygon_api.get_all_test_cases(polygon_id, testset)
        polygon_api.store_test_cases_in_redis(polygon_id, test_cases, expiry_hours=0.5)
    else:
        logger.info("Retrieved test cases from Redis for storage upload")

    storage = get_test_case_storage()
    storage.delete_problem_tests(db_problem_id)

    uploaded_count = 0
    for idx, test in enumerate(test_cases, start=1):
        input_data = test.get("input", "")
        output_data = test.get("output", "")
        if input_data and output_data:
            storage.upload_test_case(db_problem_id, idx, input_data, output_data)
            uploaded_count += 1
        else:
            logger.warning("Skipping test case #%s because input or output is empty", idx)

    if uploaded_count == 0:
        raise RuntimeError("No test cases were uploaded.")

    logger.info("Uploaded %s test cases for problem %s", uploaded_count, db_problem_id)
    return uploaded_count, storage.problem_folder_url(db_problem_id)
