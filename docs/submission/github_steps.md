# GitHub steps (click by click)

You need: your GitHub login, and Git installed. The AI did not create any account and did not push anything.

## Part 0. Secret scan (done for you)

Scanned: the working tree of `main`, and every commit in the history (all revisions).
Patterns: Groq, Slack, GitHub, OpenAI-style and AWS keys; private-key blocks; `KEY=`, `TOKEN=`, `SECRET=`, `SALT=` assignments with a long value.

- **Files with a real key, token or salt: none found.**
- One file matched the pattern and is a false alarm: `core/graph/hashing.py`. It only holds the *name* of the setting (`HEARTHGUARD_HASH_SALT`), not a value.
- `.env.example` is tracked and holds names only.
- `.env` was never committed. No `.env`, `.pem` or `.key` file was ever added to any commit (only `.env.example`).
- `.gitignore` covers `.env` (line 1) and `data/raw/` (line 2). Checked with `git check-ignore`: both are ignored.

Limit: this scan is pattern-based. A secret in an odd format could slip past. Before you push, run this yourself and read the file names:

```
git log --all --name-only --format= | sort -u | grep -iE "\.env|secret|token|\.pem|\.key"
```

Expected: only `.env.example`. If you ever pasted a Groq or Slack key into a chat, rotate it later.

## Part 1. Create the empty repo on the website

1. Go to https://github.com and log in.
2. Click the **+** at the top right, then **New repository**.
3. In **Repository name** type `hearthguard`.
4. Choose **Public**.
5. Leave all three boxes empty: no README, no .gitignore, no license. (Your project already has these files; ticking them causes a clash.)
6. Click **Create repository**.
7. Keep the page open. Copy the address that looks like `https://github.com/YOUR-NAME/hearthguard.git`.

## Part 2. Push `main` from your computer

Open PowerShell in `C:\Users\farze\newhackathon`. Run `git status`. It should show only the three `.bak` files as untracked. Do not add them.

```
git checkout main
git remote add origin https://github.com/YOUR-NAME/hearthguard.git
git push -u origin main
```

If Windows asks you to log in, use the browser window that opens. Never paste a token into a file in the repo.

To include this submission folder, merge the branch yourself first (the AI did not merge):

```
git merge coding/s4-submission
git push
```

Check: refresh the GitHub page. You should see README.md, demo, docs, core and the rest. Click `.env.example` and confirm it holds names only. The folder `data/raw` must not be there.

## Part 3. Turn on GitHub Pages from /demo

1. On the repo page click **Settings** (tab at the top).
2. In the left list click **Pages**.
3. Under **Build and deployment**, find **Source** and choose **Deploy from a branch**.
4. Under **Branch** choose `main`.
5. In the folder box next to it choose `/demo`. If the list only shows `/ (root)` and `/docs`, use "If /demo is not offered" below.
6. Click **Save**.
7. Wait one to three minutes and refresh the Pages screen. A box says "Your site is live at https://YOUR-NAME.github.io/hearthguard/".
8. Open that link in a private window. You should see the Hearthguard demo.

If /demo is not offered (GitHub often lists only `/ (root)` and `/docs`), run:

```
git checkout main
git subtree push --prefix demo origin gh-pages
```

Then in Settings, Pages, choose branch `gh-pages` and folder `/ (root)`. This pushes a copy of the `demo` folder to a branch named `gh-pages`.

## Part 4. Last checks

- Open the Pages link, then turn Wi-Fi off and reload. The page should still show, because it loads no outside files (checked: no script, image, font or stylesheet link to the web).
- Copy two links for the form: the repo link and the Pages link.
- The repo is public as soon as you create it. Do not share the links before you are ready.
