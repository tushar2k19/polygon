# Polygon migration tool

Staff work on one page, Hatsu: Problem Migrator, at `/`. `problems.views.index` handles every button. Fetch, save, test descriptions, and the file upload all post to that view.

On a save or an upload, the view refreshes the statement from Polygon before it writes the problem or the test rows. The file upload runs before that refresh. Test-description rows are written last. If something in that block fails, the banner reads "Migration failed and all changes have been rolled back." plus the reason, and the database writes are undone.

Storage here is Google Drive, `STORAGE_PROVIDER=gdrive`. The Azure path is still in `index` when that setting is anything else.

## Login

**Click or submit.** Email and password on `/users/login/`.

**Sent to the server.** Those two fields, and the CSRF token.

**Server, in order.** `login_view` drops any session already open. `EmailBackend` finds the user by email and checks the password. Staff are redirected to `/`.

**External APIs.** None.

**Database or storage.** Reads the user. Django writes the session.

**What you see.** "Welcome" and your name, then the Polygon id box. A wrong password says "Invalid email or password." An account that is not staff says "You do not have staff access." Logout posts to `/users/logout/` and comes back to the login page.

## Fetch a problem

**Click or submit.** Type a Polygon problem id and click Fetch Problem. I used 634034.

**Sent to the server.** `problem_id`.

**Server, in order.** If the problem is already saved, the main solution is read first: `problem.solutions` (the one tagged MA, otherwise the first) and `problem.viewSolution`. Then `download_and_extract_package` takes the latest standard package. It reads `problem.html` when the zip has it, and `statements/english/problem-properties.json` when it does not. Fetch is the button that always downloads every test, through `get_all_test_cases`, and keeps them in Redis for 30 minutes. The checker name has `std::` and `.cpp` removed. Anything that is not a known checker is stored as `custom`.

**External APIs.** `problem.info`, `problem.packages`, `problem.package`, `problem.tests`, `problem.testInput`, `problem.testAnswer`, and `problem.checker`. When the row already exists, also `problem.updateWorkingCopy`, `problem.solutions`, and `problem.viewSolution`.

**Database or storage.** Postgres is not written. Redis holds the tests.

**What you see.** The statement, limits, checker, and a test table. A cell longer than 50 characters gets View Full. Until you save, Database Problem ID and the Algopath link say "Please migrate to database first." The solution panel says the same, and the storage and test-description buttons stay disabled. The loading line says the fetch may take 3–4 minutes.

## Save the problem

**Click or submit.** Choose easy, medium, or hard, add tags, and click Create/Update problem in Database. The page blocks an empty difficulty before the request goes out.

**Sent to the server.** `problem_id`, `migrate_to_db=1`, `difficulty`, and one `tags` field per tag.

**Server, in order.** The statement is refreshed. Tests come from Redis while the cache is warm, and from Polygon only if it is not. A missing difficulty is rejected. An existing polygon id is updated. A new one is created. The tags you sent replace the ones already on the problem. Sample tests, the ones Polygon includes in the statement, are saved whole. The solution is read again after the save, this time without `problem.updateWorkingCopy`.

**External APIs.** The same package and checker calls as fetch. Test files only if Redis missed. Then `problem.solutions` and `problem.viewSolution`.

**Database or storage.** The problem row, its tags, and the sample rows.

**What you see.** A blue Database Operation banner: "Problem '{title}' created in database successfully." or "Problem '{title}' updated in database successfully." The database id and `https://www.algopath.ai/problems/{slug}` show up, and the solution has a Copy button. The other two buttons turn on.

## Save test descriptions

**Click or submit.** Migrate Test Description to Database, after the problem is saved.

**Sent to the server.** `problem_id` and `migrate_test_cases_to_db=1`.

**Server, in order.** Same refresh, Redis first. Each test that has both an input and an output is written to `ProblemTestCase`. Input and output are cut at 260 characters. The description is kept. Rows are matched by position and numbered from 1. The sample rows from the save step are a different table, and those are not cut.

**External APIs.** Polygon for the statement refresh. Test files only on a Redis miss.

**Database or storage.** `ProblemTestCase` rows.

**What you see.** "Test cases description migrated to database Successfully."

## Upload the test files

**Click or submit.** Migrate Test Cases to Google Drive. On Azure the button says Migrate Test Cases to Azure.

**Sent to the server.** `problem_id` and `migrate_to_azure=1`. The field is still named `migrate_to_azure` when the files go to Drive.

**Server, in order.** If there is no database row, the view stops. The error still says Azure, and the page is not refreshed. With a row, the folder uses the database id, not the Polygon id. Drive calls `upload_problem_tests` in `problems/storage.py`: read the cached tests, delete the old files for that problem, upload each pair. It does not upload a checker. The Azure branch calls `migrate_to_azure_blob` and can compile and upload a custom checker.

**External APIs.** Google Drive, or Azure. After a successful upload the page is refreshed from Polygon. Test files are downloaded again only if the cache has expired.

**Database or storage.** Full files at `test_cases/{database id}/01` and `01.a`, two digits, one pair per test. For 634034 that was database id 1, `01` through `15`. Postgres is not changed. A separate Redis cache for that database id, `oj_dev_with_redis_storage_test_cases_{id}`, is cleared.

**What you see.** "Test cases migrated to Google Drive successfully ({count} test cases)." and the folder link. Azure says "Test cases migrated to Azure Blob Storage successfully."

## Polygon auth and file names

Every Polygon call is a POST to `https://polygon.codeforces.com/api/` plus the method. The app will not start without `POLYGON_API_KEY` and `POLYGON_API_SECRET`. `apiSig` is a 6-character prefix plus a SHA-512 of the method, the sorted parameters, and the secret. The methods are the ones named in the flows above. A custom checker on the Azure path also uses `problem.viewFile`.

Drive files sit under `GOOGLE_DRIVE_FOLDER_ID`. Input is `test_cases/{database id}/{test number}`. Output is the same name with `.a`.

