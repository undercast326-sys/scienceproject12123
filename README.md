# CookUNT

CookUNT — Django REST API + vanilla JS app for ЕНТ (UNT) prep.

Content structure: **Subject → Topic → Paragraphs (theory) + Tasks**, plus authored, timed **Mock tests** per subject. Users read paragraphs, practise tasks with instant feedback, sit mock tests in exam conditions (countdown, no hints, review at the end), and earn XP/levels.

## Adding content (admin)

Everything is managed at `<backend-url>/admin/`:

- **Subjects** → **Topics** (each topic page has inline editors for its Paragraphs and Tasks).
- **Mock tests** → one per exam variant; set `Subject`, `Duration minutes`, and add its Questions inline. Untick `Is published` to hide a draft.
- Task/question fields: `type` = `single` / `multiple` / `text`. Type `options` as plain text, **one option per line** (leave empty for `text`). Type `correct_answer` as the exact text of the right option; for `multiple`, one correct option per line; for `text`, the expected answer (case-insensitive). Saving fails if the answer doesn't match the options. `explanation` is shown after answering.
- XP: 10 per question answered correctly **for the first time** (practice and mock tests alike). Replaying already-solved questions updates stats but gives no XP.

## Maths content from Word files

The Математика subject is generated from the chapter `.doc` files (Word 97–2003, formulas in Equation Editor 3.0). The `.doc` files are not committed: they stay local, and `*.doc` is in `.gitignore`. Their content is committed instead, in `backend/content/math.json`.

- **One file = one topic.** Each `NN.NN` subsection becomes a theory paragraph, and all of the file's A–E tests become the topic's tasks.
- **Formulas** are converted to LaTeX (`$...$`) and drawn on the site with KaTeX. Word tables become `[table]` blocks (rows on lines, cells split by tabs), and `### ` lines are subheadings.
- **Skipped tasks.** A task is left out if it uses a picture, if a formula can't be read, or if its options are identical after conversion. About 6% are skipped; the script prints the counts by reason.

To rebuild after editing or adding `.doc` files:

```bash
python3 -m venv /tmp/docenv && /tmp/docenv/bin/pip install -r tools/doc_import/requirements.txt
/tmp/docenv/bin/python -I tools/doc_import/build_math.py . backend/content/math.json
```

Topic names live in `TOPICS` in `tools/doc_import/build_math.py`.

**Importing.** On every deploy, `python manage.py import_content content/math.json` runs at start. It does nothing if the file is unchanged since the last import. When the file changes, it **replaces all Математика topics**: tasks, paragraphs and students' progress on them. Edits made to those topics in the admin are lost too, so for lasting changes edit the `.doc` files (or the JSON) instead. Other subjects are not touched. Use `--force` to reimport an unchanged file.

## Mock tests (ЕНТ variants)

`backend/content/math_mock.json` holds 5 variants for Математика, with 40 tasks each. `backend/content/matgram_mock.json` holds 20 variants for Математическая грамотность, with 10 tasks each. Both were transcribed by hand from the PDF collection (the PDFs aren't committed), with formulas written in LaTeX.

- **Matching tasks** (31–35 in Математика) are split into one single-choice question per item, so each mock has 45 questions.
- **Multiple-choice tasks** (36–40) use type `multiple`.
- **Figures** live in `frontend/content-img/mock/`. A prompt references one as `[img:content-img/mock/<file>.png]`.

These files load through the same `import_content` command as `math.json`. A file that has only `mock_tests` replaces only that subject's mock tests: topics and theory are not touched. Each file is tracked separately, so changing one file reimports only that file.

## Deploy (Render)

1. Push this folder to a new GitHub repo (see commands below).
2. On [render.com](https://dashboard.render.com), click **New > Blueprint**, connect the repo, and click **Apply**. Render reads `render.yaml` at the repo root and provisions three things automatically:
   - `science-quiz-db` — a Postgres database
   - `science-quiz-backend` — the Django API (migrations run and an admin superuser is created automatically on every deploy)
   - `science-quiz-frontend` — the static frontend, wired to the backend's URL automatically at build time
3. Once deployed, open the `science-quiz-frontend` service's URL. That's the app.
4. The admin panel is at `<backend-url>/admin/`. Username is `admin`; the password was auto-generated — find it in the Render dashboard under the backend service's **Environment** tab (`DJANGO_SUPERUSER_PASSWORD`).

**Two things to know:**
- Render's free Postgres plan **expires 30 days after creation** (then a 14-day grace period before deletion). Upgrade the database to a paid plan before then if you want to keep the data.
- The seeded content is placeholder/test data only (`Тестовая тема 1/2` per subject and one `Пробный вариант`). Add real content through `/admin/`, or write your own version of `backend/apps/topics/management/commands/seed_test_data.py` and run it from the Render Shell tab (`python manage.py seed_test_data`) — note it wipes and reseeds the curriculum tables, so don't run it once real content exists.

### Push to GitHub

```bash
cd "science project"
git init
git add .
git commit -m "Initial commit"
gh repo create science-quiz --private --source=. --push
# or, without the gh CLI:
# git remote add origin git@github.com:<you>/science-quiz.git
# git branch -M main
# git push -u origin main
```

## Local development

Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults already work for local dev
python manage.py migrate
python manage.py ensure_superuser   # creates admin/admin12345 from .env
python manage.py seed_test_data     # optional: placeholder topics/questions
python manage.py runserver
```

Frontend:
```bash
cd frontend
python3 -m http.server 5500
```

Open http://127.0.0.1:5500. The frontend talks to `http://127.0.0.1:8000/api` by default in local dev.
