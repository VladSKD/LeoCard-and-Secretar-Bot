# Deploying to EC2

This document covers everything that's NOT captured in Terraform: the
first-time setup inside the instance, the secrets layout, the self-hosted
GitHub Actions runner, and the Google credentials generation dance.

Prerequisites (on your laptop):
- Terraform already ran (`make tf-apply`) and you can SSH in.
- You have generated `credentials.json` + `token.json` for the Leocard
  and Profcom Google accounts on your laptop (instructions below).
- You have created a Service Account for the tickets bot and downloaded
  its JSON key.

## 1. Lay out the secrets on the box

SSH in once and run:

```bash
sudo mkdir -p /etc/telegram-bots/{leocard,profcom,tickets}
sudo chown -R ec2-user:ec2-user /etc/telegram-bots
chmod 700 /etc/telegram-bots
```

Then scp the files from your laptop:

```bash
# From your laptop:
scp .env                                          ec2-user@<EIP>:/etc/telegram-bots/.env
scp leocard_credentials.json                      ec2-user@<EIP>:/etc/telegram-bots/leocard/credentials.json
scp leocard_token.json                            ec2-user@<EIP>:/etc/telegram-bots/leocard/token.json
scp profcom_credentials.json                      ec2-user@<EIP>:/etc/telegram-bots/profcom/credentials.json
scp profcom_token.json                            ec2-user@<EIP>:/etc/telegram-bots/profcom/token.json
scp tickets_service_account.json                  ec2-user@<EIP>:/etc/telegram-bots/tickets/service_account.json
```

Back on the box:

```bash
chmod 600 /etc/telegram-bots/.env \
          /etc/telegram-bots/*/credentials.json \
          /etc/telegram-bots/*/token.json \
          /etc/telegram-bots/tickets/service_account.json
```

Persistent data directory (survives redeploys):

```bash
sudo mkdir -p /var/lib/telegram-bots/data/{leocard/bot_persistence,profcom/generated_petitions}
echo '{}' | sudo tee /var/lib/telegram-bots/data/profcom/notification_chats.json > /dev/null
sudo chown -R ec2-user:ec2-user /var/lib/telegram-bots
```

## 2. Install the GitHub Actions self-hosted runner

On GitHub: **repo → Settings → Actions → Runners → New self-hosted runner → Linux x64**.
GitHub will give you a one-line registration token — copy it now, it
expires in an hour.

On the EC2 box:

```bash
# Download and unpack the runner (check releases page for latest tag)
mkdir -p ~/actions-runner && cd ~/actions-runner
RUNNER_VERSION=2.320.0   # update as needed
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Configure the runner. The labels MUST match the workflow's runs-on list.
./config.sh \
  --url https://github.com/<your-user>/<your-repo> \
  --token <TOKEN_FROM_GITHUB_UI> \
  --name telegram-bots-ec2 \
  --labels self-hosted,linux,x64,telegram-bots \
  --unattended

# Install and start as a systemd service
sudo ./svc.sh install ec2-user
sudo ./svc.sh start
sudo ./svc.sh status
```

Give the runner user passwordless `sudo` for the two commands the
workflow needs (creating and chowning `/var/lib/telegram-bots/data`):

```bash
echo 'ec2-user ALL=(root) NOPASSWD: /bin/mkdir, /bin/chown, /usr/bin/tee' \
  | sudo tee /etc/sudoers.d/telegram-bots-runner
sudo chmod 440 /etc/sudoers.d/telegram-bots-runner
```

(If you're uncomfortable with sudo, skip this and pre-create the
directories once — the workflow's `sudo mkdir -p` calls are idempotent
and will succeed as no-ops.)

Docker group for the runner so it doesn't need sudo for `docker compose`:

```bash
sudo usermod -aG docker ec2-user
# Log out and back in for the group change to take effect, or just:
sudo systemctl restart actions.runner.*
```

## 3. Push to main — deploy happens automatically

That's it. Any push to `main` triggers `.github/workflows/deploy.yml`:

1. The runner checks out the latest commit (in its own workspace).
2. It symlinks `.env` and the credential files from `/etc/telegram-bots/`.
3. It symlinks the persistent `data/` subtrees from `/var/lib/telegram-bots/data/`.
4. It runs `docker compose build` + `docker compose up -d --remove-orphans`.
5. It prunes dangling images (critical on t3.micro — disk fills fast).
6. It smoke-tests that every container is in `running` state and
   fails the build if any is not.

You can also trigger deploys manually from the GitHub UI via the
**Run workflow** button (`workflow_dispatch`).

## 4. Generating Google credentials (one-off)

### Leocard and Profcom (OAuth 2.0, user-type)

Both bots use OAuth 2.0 installed-app flow. On your LAPTOP (never on
the server — there's no browser there), run a one-off Python script
against each bot's `credentials.json` (the client secret you downloaded
from Google Cloud Console):

```python
# bootstrap_token.py — run locally, once per bot
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.json", "w") as f:
    f.write(creds.to_json())
print("wrote token.json")
```

This opens a browser, you log in to the Google account you want the bot
to act as, approve the scopes, and `token.json` lands on your disk. scp
it to `/etc/telegram-bots/<bot>/token.json` on the server.

**After that, refreshes happen automatically.** The google-auth library
detects when the access token expires, uses the refresh token to get a
new one, and writes the updated `token.json` back through the
bind-mount — so the refresh persists across container restarts without
you touching anything.

The only time you need to regenerate `token.json` manually is if:
- You explicitly revoke access in your Google account settings.
- Your Google Cloud project is still in "Testing" mode and 7 days
  passed without use (then the refresh_token expires — move the app
  to "In production" in the OAuth consent screen to fix).
- The `credentials.json` client secret itself is rotated.

### Tickets (Service Account)

Service accounts are much simpler — no browser flow, no refresh dance,
no expiration.

1. **Google Cloud Console → IAM & Admin → Service Accounts → Create Service Account.**
   Name it something like `tickets-bot`. Skip role assignments.
2. Open the new service account → **Keys → Add Key → Create new key → JSON.**
   A file downloads. This is `service_account.json`.
3. Open the target Google Sheet (the one whose ID goes into
   `TICKETS_SHEET_ID`). Click **Share** and add the service account's
   email address (looks like `tickets-bot@<project>.iam.gserviceaccount.com`)
   as **Editor**. The service account can only see sheets it's explicitly
   shared with.
4. scp the file to `/etc/telegram-bots/tickets/service_account.json` on
   the server. Done. This file never needs rotation unless you want to.

## 5. Redeploying

```
git push origin main
```

The runner will rebuild the affected images, restart the containers,
and verify they're alive. Total downtime per bot: a few seconds.

If you want to roll back:

```
git revert HEAD && git push origin main
```

## 6. Troubleshooting

**"make doctor" complains about empty files locally.**
That's fine on the EC2 box as long as `/etc/telegram-bots/…` has the
real files. `make doctor` is for local development only — the deploy
workflow does its own pre-flight checks.

**Runner is offline on GitHub UI.**
```bash
sudo systemctl status actions.runner.*
sudo journalctl -u actions.runner.* -n 100
```

**Container keeps restarting.**
```bash
docker compose logs --tail=200 <bot>
```
Most common cause: `make doctor` would have caught it on your laptop —
either a missing credential file or a typo in `.env`.

**Google refresh token got invalidated.**
Regenerate `token.json` on your laptop (section 4), scp it to
`/etc/telegram-bots/<bot>/token.json`, trigger a manual deploy from
the GitHub UI (so the container picks up the new file via its
bind-mount). No code changes needed.
