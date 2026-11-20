# Issues Analysis

> **Instructions**: Document the three highest-priority product issues and the three highest-priority code issues. Rank the issues within each category from highest to lowest priority.
> Replace the example entries with your actual findings and explain why each issue deserves its priority. Complete all four questions in the Edge Case Analysis section.
> Rename this file to `ISSUES.md` before submitting.

## Summary

| Type | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Product Issues | 1 | 2 | 0 | 0 | 3 |
| Code Issues | 1 | 3 | 0 | 0 | 4 |

---

## Product Issues

> Product issues are user-facing problems: broken functionality, missing validation, poor UX, data integrity risks visible to users.

### [P1] Tag names can break the page and run script (stored XSS)

**Severity**: Critical

**Location**: `problems/templates/problems/index.html:365-366` and `:575`

**Description**:
The tag list is printed into the page's `<script>` block with `|safe`, and the selected tag chips are built with `innerHTML` and an inline `onclick`. On save, each tag is stripped and a blank name is skipped, and the column rejects a name longer than 100 characters. Nothing rejects `<` or a quote. I saved a tag whose name closed the script block and set the tab title. On the next load of the home page the title changed, and the rest of the page script showed up as plain text on screen.

**Impact**:

- The tag is stored once and loads for every staff user, so one bad tag hits everyone
- Injected script runs inside a logged-in staff session and can submit the migrate forms on their behalf
- The Fetch and migrate forms sit above that script and still submit. Tag picking, the difficulty copy, and the loading overlay stop, and the rest of the script is shown as text, until the tag is removed in admin

**Why this rank**: One saved tag runs for every staff user. P2 and P3 keep the wrong test data, and they do not run script.

**Suggested Fix**:
Output the tags with Django's `json_script` filter instead of `|safe`. Build the chips with `textContent` and `addEventListener`, not `innerHTML` or inline `onclick`. The 100-character limit is already there. Also reject `<` and quotes before saving.

**Evidence**: `evidence/p1-tag-script-breaks-page.png`

---

### [P2] Re-migrating a problem leaves removed test cases in the database

**Severity**: High

**Location**: `problems/views.py:548-582`

**Description**:
"Migrate Test Description to Database" updates the existing rows one by one and adds rows if there are more tests. It never deletes extra rows. I migrated a problem with 12 tests, removed 4 on Polygon, and migrated again. The fetch page and the Google Drive upload both show 8 tests, but the database still has 12. Rows 9 to 12 keep the old data. The "Test Case Count" cell on the page shows the live Polygon count, which was 8. The stored `Problem.test_case_count` stays 12, because this button never writes it (`views.py:387` writes it only on Create/Update). Both buttons show a green success message.

**Impact**:

- The database holds tests that no longer exist on Polygon, and no one is told
- Database and Drive now disagree for the same problem
- A later read of these rows still returns the removed tests

**Why this rank**: A shorter problem leaves old tests behind on every re-migrate. P3 only cuts a test that is already longer than 260 characters.

**Suggested Fix**:
Inside the same transaction, delete the rows past the last one written (or clear and recreate them). Set the stored `test_case_count` from the new count. The cell on the page already shows the live Polygon count.

**Evidence**: `evidence/p2-fetch-and-drive-show-8-tests.png` (8 total) and `evidence/p2-admin-still-has-12-rows.png` (12 rows)

---

### [P3] Long test inputs and outputs are cut at 260 characters without a warning

**Severity**: High

**Location**: `problems/views.py:557-559`

**Description**:
Before saving, each test's input and output goes through `rstrip()`, which removes all trailing whitespace, and that text is then sliced with `[:260]`. The comment says "bytes" but the code counts characters. On my test problem, test 11 is 305 bytes in the Google Drive file, but the database row holds 260 characters. The page still says "Test cases description migrated to database Successfully." The model fields are `TextField`, so the database does not need this limit.

**Impact**:

- Large tests are saved incomplete and wrong, which is exactly where tests matter
- Drive and database hold different versions of the same test
- Nothing on screen tells the user that data was dropped

**Why this rank**: The cut is silent and real, and it only applies once the text is longer than 260 characters. The orphan rows in P2 happen on an ordinary re-migrate.

**Suggested Fix**:
Remove the slice and store the full text. If a size limit is needed, reject the test with a clear message and don't report success.

**Evidence**: `evidence/p3-fetch-page-test-11.png` (full test on the fetch page) and `evidence/p3-admin-test-11-stored-at-260.png` (saved row, 260 characters)

---



---

## Code Issues

> Code issues are technical problems: bugs, security vulnerabilities, performance problems, code quality concerns, architectural issues.

### [C1] A failed file upload deletes the old files, hides the error, and says success

**Severity**: Critical

**Location**: `problems/polygon_api.py:821-830`, `problems/AzureTestcase.py:80-81`, `problems/views.py:261-264`

**Description**:
`migrate_to_azure_blob` first calls `empty_blob`, which deletes every file for the problem, and only then uploads the new ones. `upload_test_case` wraps its work in `except Exception` and only writes to the log, so the caller never learns that an upload failed. The loop still does `uploaded_count += 1`, and the view then sets "Test cases migrated to Azure Blob Storage successfully." This is the Azure branch. The Drive upload raises if nothing was uploaded, so it does not hide a total failure the same way. I haven't run this against a real Azure account. I used a fake storage client that fails every upload: it deleted the 4 files that were already there, all 8 uploads failed, and the page still showed the green success message.

**Impact**:

- The last good set of files is gone before the new one is safe
- A failed run can leave the folder empty or half full, and the page says it worked
- Clicking again repeats the delete, so the damage is hard to notice and hard to trace

**Why this rank**: The last good files are deleted and the page says the upload worked. The other three leave the wrong text or the wrong cache key, and they do not throw away the last good files on a failure.

**Suggested Fix**:
Let upload errors raise, count only uploads that succeeded, and fail the request if any failed. Upload the new files first and remove leftover old ones only afterwards.

---

### [C2] Saving the problem again erases the constraints and editorial typed in admin

**Severity**: High

**Location**: `problems/views.py:320-321`, `:344`, `:382-383`, and `:389`

**Description**:
Every fetch sets `constraints` and `editorial` to `''`. The package parse does not fill those two. On "Create/Update problem in Database" the empty strings are written onto the existing row. I typed both by hand on a test problem (constraints `1 <= a, b <= 1000`, editorial `Add the two numbers`) and clicked update once. Both came back empty. The page said "Problem '{title}' updated in database successfully." That banner is the blue info alert (`index.html:147-150`), not the green success alert. `notes` is different: line 344 reads Polygon's note block, and line 389 writes that over whatever was typed. It is empty only when Polygon has no note. Nothing on the page says constraints or editorial will be cleared.

**Impact**:

- Constraints and editorial typed in admin are gone, and Polygon has no copy of them to restore from
- A normal re-save, for a title or a time limit, clears those two every time
- The info banner gives no hint that those fields were touched

**Why this rank**: Every database save clears those two fields. C3 only happens while a Redis copy from the last 30 minutes is still there.

**Suggested Fix**:
On update, leave `constraints` and `editorial` alone. Keep writing `notes` from Polygon's note block. Overwrite constraints or editorial only when a value was actually sent for them.

---

### [C3] The Drive button can upload an old copy of the tests

**Severity**: High

**Location**: `problems/storage.py:65-74`, `problems/views.py:212-226`, and `problems/polygon_api.py:907`

**Description**:
"Migrate Test Cases to Google Drive" reads Redis before it asks Polygon. If a copy is sitting there, that copy is what gets uploaded. The copy lasts 30 minutes (`expiry_hours=0.5`, stored with `setex` for 1800 seconds). I left a 1-test copy in Redis for Polygon problem 634422, which really had 8 tests, and clicked the Drive button. The storage stand-in was told to delete the existing files and then write one file, `STALE 1 1`. The page said "Test cases migrated to Google Drive successfully (1 test cases)." The full string also appends `Folder: {url}`.

**Impact**:

- Change a test on Polygon and click Drive inside that half hour, and the old test is what lands in the folder
- The files already in Drive are deleted first, so the good copy is replaced, not kept beside the old one
- The count is in the banner, so "(1 test cases)" and "(8 test cases)" are different text. It is still easy to treat the green banner as proof the upload was current

**Why this rank**: This button replaces the Drive files. C4 is why the refresh before that upload misses, and it has a separate wildcard, but the files change here.

**Suggested Fix**:
For this button, fetch the tests from Polygon instead of trusting Redis. If a cache is kept, clear the key this app actually writes (C4) before the upload, and fail the request when the uploaded count doesn't match Polygon.

---

### [C4] The "forget the old copy" step forgets the wrong copy

**Severity**: High

**Location**: `problems/views.py:210` and `:592`, `problems/polygon_api.py:858`, `:903`, and `:1003`

**Description**:
Just before the upload, the view calls `delete_problem_test_case_cache` with the database id. That function deletes `oj_dev_with_redis_storage_test_cases_{db id}*`. This app stores its copy as `polygon_migration_test_cases_{polygon id}`, so the delete never matches and the next read still hits Redis. I ran that delete for id `999001`: this app's key was still there. A different function, `clear_test_cases_from_redis`, uses the right prefix but builds `{prefix}*` with no separator, so a scan for `999001` also matches `9990011`. When I ran that clear, it deleted the `9990011` key too. The Drive success path does not call it. The exception handler does, at `views.py:592`. The mismatched delete is why C3 can upload a stale copy. On a miss, the first function logs the pattern it scanned. The second logs `Cleared {n} test case keys`.

**Impact**:

- The refresh before every Drive upload does nothing to this app's copy
- The other clear, used when a save fails, can also wipe another problem whose id starts the same way (`1` matches `10`, `11`, `100`)
- The page shows nothing about either miss. The log lines name the pattern or the count. They do not say only that a clear ran

**Why this rank**: The visible damage is the stale Drive upload in C3. This entry is the wrong key that lets that happen, and a second pattern that can clear a neighboring id.

**Suggested Fix**:
Call `clear_test_cases_from_redis(polygon_id)` before the upload, and put a `_` after the id in the pattern (`..._999001_*`) so it cannot match `9990011`.

---

## Edge Case Analysis

### Q1

> A Polygon problem has 0 sample test cases but 15 regular test cases. What happens when you migrate this problem?

I tried this with a problem that had no samples and 12 regular tests. The fetch page marked every test as not a sample. Saving worked, with the normal success message, and no sample rows were created. The regular tests still migrated to the database and to Drive. Nothing told me the problem had no examples. Fifteen regular tests would do the same.

---

### Q2

> A problem is migrated with 20 test cases. Later, the problem setter removes 8 test cases on Polygon (now 12 remain). The problem is re-migrated. What happens?

I checked this by going from 12 tests down to 8. After migrating again, the fetch page and Google Drive both showed the smaller set, and both buttons said success. The database still had the old extra rows, with the tests that were already deleted on Polygon. Going from 20 to 12 does the same thing: Drive ends up with 12, and the database still has all 20.

---

### Q3

> Two different Polygon problems have the exact same title: "Two Sum". You migrate the first one successfully. Then you try to migrate the second one. What happens?

The first one saves. The second one does not. I hit this with two problems both titled "Sum of Two Integers". The page said the migration was rolled back because the slug `sum-of-two-integers` already exists. The first problem was left as it was. I had to rename the second one on Polygon before it would save. "Two Sum" would fail the same way, on the slug `two-sum`.

---

### Q4

> When test cases are saved to the database via "Migrate Test Cases to DB", some data is intentionally discarded. What data is lost? Why might this cause problems?

The button in the app is "Migrate Test Description to Database". It cuts each test's input and output at 260 characters, and it also strips spaces at the end. The page still says the migration succeeded. I had a test that was 305 characters in the Drive file and only 260 in the database. A long test is stored incomplete, and the Drive copy and the database copy no longer match. Nothing tells you the text was cut.

---

## Severity Guidelines

Use these definitions when assigning severity:

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical** | System broken, security vulnerability, data loss | SQL injection, authentication bypass, data corruption |
| **High** | Major functionality broken, significant data integrity risk | Feature doesn't work, orphaned records, race conditions |
| **Medium** | Feature partially broken, poor UX, code maintainability | Missing validation, confusing errors, code duplication |
| **Low** | Minor issues, cosmetic, best practice violations | Unused imports, inconsistent formatting, missing logs |

---

## Notes

[Add any additional observations, patterns you noticed, or architectural concerns that don't fit into specific issues above]
