
# Wyze Connect Sync
***

<p align="center">
  <img width="25%" src="https://user-images.githubusercontent.com/22617546/208175452-dbbff5b9-59ce-4ffc-a255-698617c94de0.jpg" />
</p>

[![Stars](https://img.shields.io/github/stars/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/stargazers)
[![Version](https://img.shields.io/github/v/release/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/releases/latest)
[![Commits Since Latest Release](https://img.shields.io/github/commits-since/svanhoutte/wyze_garmin_sync/latest)](https://github.com/svanhoutte/wyze_garmin_sync/commits/master)
[![Latest Release Date](https://img.shields.io/github/release-date/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/releases/latest)
[![Open Issues](https://img.shields.io/github/issues-raw/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/issues?q=is%3Aopen+is%3Aissue)
[![Closed Issues](https://img.shields.io/github/issues-closed-raw/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/issues?q=is%3Aissue+is%3Aclosed)

[![PayPal](https://img.shields.io/badge/PayPal-Donate-green)](https://paypal.me/SVanhoutte79?country.x=US&locale.x=en_US)
[![Buymeacoffee](https://badgen.net/badge/icon/buymeacoffee?icon=buymeacoffee&label)](https://www.buymeacoffee.com/sebastienv)



***

# Wyze Garmin Sync

Automatically synchronize body-composition measurements from a **Wyze Scale** to **Garmin Connect**.

The application retrieves the latest measurement from your Wyze account and uploads the body-composition data to Garmin Connect.

The Docker container performs a synchronization when it starts and then checks for new measurements every **10 minutes**.

---

## Features

- Automatic Wyze Scale discovery
- Synchronizes the latest Wyze Scale measurement to Garmin Connect
- Supports body-composition data including:
  - Weight
  - Body fat
  - Body water
  - Bone mass
  - Muscle mass
  - Basal metabolic rate
  - Active metabolic rate
  - Metabolic age
  - Visceral fat rating
  - BMI
  - Physique/body type
- Persistent Wyze authentication tokens
- Persistent Garmin authentication tokens
- Garmin MFA / two-factor authentication support
- Automatic Garmin token refresh
- Automatic Wyze token refresh
- Duplicate measurement detection
- Automatic execution every 10 minutes
- Docker deployment

---

# Authentication

Both Wyze and Garmin use persistent authentication tokens.

This is important because repeatedly performing username/password authentication can trigger API rate limits from both services.

The Docker container therefore stores authentication information in:

```text
/wyze_garmin_sync/tokens
```

The Docker Compose configuration maps this to:

```text
./tokens
```

on the Docker host.

After the initial authentication, the directory should contain files similar to:

```text
tokens/
├── wyze_tokens.json
└── garmin_tokens.json
```

Do **not** delete this directory unless you intentionally want to authenticate again.

---

# Wyze Authentication

Wyze requires the following environment variables:

```text
WYZE_EMAIL
WYZE_PASSWORD
WYZE_KEY_ID
WYZE_API_KEY
WYZE_TOKEN_FILE
```

A Wyze API Key and Key ID must be created for your Wyze account.

The default token location used by the container is:

```text
/wyze_garmin_sync/tokens/wyze_tokens.json
```

This is configured with:

```yaml
WYZE_TOKEN_FILE: "/wyze_garmin_sync/tokens/wyze_tokens.json"
```

The application performs a full Wyze username/password authentication only when a cached token does not already exist.

After the first successful authentication it creates:

```text
tokens/wyze_tokens.json
```

Subsequent executions reuse the stored access token.

If the Wyze access token expires, the application attempts to refresh it using the stored refresh token instead of performing another username/password login.

This helps prevent Wyze authentication rate limiting such as:

```text
429 Client Error: Too Many Requests
```

---

# Garmin Authentication

Garmin authentication is handled using **python-garminconnect**.

Older releases of this project used Garth. Garth is no longer used by the current Docker implementation.

The Garmin token directory can be configured with:

```text
GARMINTOKENS
```

The Docker configuration uses:

```yaml
GARMINTOKENS: "/wyze_garmin_sync/tokens"
```

After successful Garmin authentication the following file is created:

```text
tokens/garmin_tokens.json
```

Normal scheduled synchronization uses this token instead of repeatedly authenticating with the Garmin username and password.

Garmin access tokens are refreshed automatically when possible.

---

## Garmin MFA / Two-Factor Authentication

If Garmin requires MFA, the initial Garmin authentication must be performed interactively.

Run:

```bash
docker compose run --rm wyzegarminconnect
```

If no valid Garmin token exists, the application detects that it is running in an interactive terminal and starts the Garmin authentication process.

If Garmin requests MFA you will see:

```text
Enter Garmin MFA code:
```

Enter the code provided by Garmin.

After successful authentication you should see:

```text
Garmin authentication successful.
Garmin token saved to /wyze_garmin_sync/tokens/garmin_tokens.json
```

The token is persisted on the Docker host as:

```text
./tokens/garmin_tokens.json
```

Future scheduled executions reuse this token and do not normally require another MFA login.

---

# Docker Installation

Docker Compose is the recommended installation method.

## 1. Create a Working Directory

For example:

```bash
mkdir wyze-garmin-sync
cd wyze-garmin-sync
```

---

## 2. Create the Persistent Token Directory

```bash
mkdir -p tokens
chmod 700 tokens
```

The directory will contain both Wyze and Garmin authentication tokens.

---

## 3. Configure Docker Compose

Example `docker-compose.yml`:

```yaml
services:

  wyzegarminconnect:

    image: svanhoutte/wyzegarminconnect:latest

    restart: unless-stopped

    network_mode: "host"

    environment:

      # --------------------------------------------------
      # Wyze
      # --------------------------------------------------

      WYZE_EMAIL: "your-wyze-email"
      WYZE_PASSWORD: "your-wyze-password"

      WYZE_KEY_ID: "your-wyze-key-id"
      WYZE_API_KEY: "your-wyze-api-key"

      # Persistent Wyze authentication token
      WYZE_TOKEN_FILE: "/wyze_garmin_sync/tokens/wyze_tokens.json"

      # --------------------------------------------------
      # Garmin
      # --------------------------------------------------

      Garmin_username: "your-garmin-email"
      Garmin_password: "your-garmin-password"

      # Persistent Garmin authentication token directory
      GARMINTOKENS: "/wyze_garmin_sync/tokens"

    volumes:

      # Container timezone
      - "/etc/timezone:/etc/timezone:ro"
      - "/etc/localtime:/etc/localtime:ro"

      # Persistent Wyze + Garmin authentication tokens
      - "./tokens:/wyze_garmin_sync/tokens"
```

Replace the example credentials with your own.

---

# Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WYZE_EMAIL` | Yes | Wyze account email |
| `WYZE_PASSWORD` | Yes | Wyze account password |
| `WYZE_KEY_ID` | Yes | Wyze API Key ID |
| `WYZE_API_KEY` | Yes | Wyze API Key |
| `WYZE_TOKEN_FILE` | No | Location of the persistent Wyze authentication file |
| `Garmin_username` | Yes | Garmin Connect username/email |
| `Garmin_password` | Yes | Garmin Connect password |
| `GARMINTOKENS` | No | Directory containing the Garmin authentication token |

The recommended Docker values are:

```text
WYZE_TOKEN_FILE=/wyze_garmin_sync/tokens/wyze_tokens.json
GARMINTOKENS=/wyze_garmin_sync/tokens
```

The application also provides defaults for the token locations, but explicitly defining them in Docker Compose makes the configuration easier to understand and customize.

---

# First Run

Stop any existing instance first:

```bash
docker compose down
```

Perform the first run interactively:

```bash
docker compose run --rm wyzegarminconnect
```

The application will:

1. Look for a cached Wyze token.
2. Authenticate with Wyze if a token does not exist.
3. Create `wyze_tokens.json`.
4. Discover the Wyze Scale.
5. Retrieve the latest scale measurement.
6. Look for a cached Garmin token.
7. Start interactive Garmin authentication if no token exists.
8. Request an MFA code if required by Garmin.
9. Create `garmin_tokens.json`.
10. Upload the latest body-composition measurement to Garmin.

After the initial authentication, verify the token files:

```bash
ls -la tokens/
```

You should normally see:

```text
wyze_tokens.json
garmin_tokens.json
```

---

# Start Normal Operation

Once both authentication tokens have been created:

```bash
docker compose up -d
```

View the logs with:

```bash
docker compose logs -f
```

The application runs automatically when the container starts and then approximately every 10 minutes.

---

# Authentication Flow

## Wyze

```text
                 Wyze authentication
                         │
                         ▼
              wyze_tokens.json exists?
                  │              │
                 YES             NO
                  │              │
                  ▼              ▼
             Load token      Wyze login
                  │              │
                  │              ▼
                  │       Save access +
                  │       refresh tokens
                  │              │
                  └───────┬──────┘
                          ▼
                     Wyze API
```

If the access token expires:

```text
Access token expired
        │
        ▼
Use refresh token
        │
        ▼
Save new tokens
```

A username/password login is not performed during every scheduled execution.

---

## Garmin

```text
                Garmin authentication
                        │
                        ▼
             garmin_tokens.json exists?
                  │               │
                 YES              NO
                  │               │
                  ▼               ▼
             Load token      Interactive?
                  │            │       │
                  │           YES      NO
                  │            │       │
                  │            ▼       ▼
                  │        Login +    Stop Garmin
                  │          MFA      upload attempt
                  │            │
                  │            ▼
                  │       Save Garmin
                  │          token
                  │            │
                  └──────┬─────┘
                         ▼
                   Garmin Connect
```

A normal background cron execution will not wait indefinitely for an MFA prompt.

If the Garmin token is missing, run:

```bash
docker compose run --rm wyzegarminconnect
```

to perform interactive authentication.

---

# Synchronization Flow

```text
Wyze Scale
    │
    ▼
Wyze API
    │
    ▼
Latest body-composition measurement
    │
    ▼
Generate measurement checksum
    │
    ├── Same measurement
    │        │
    │        └── No upload
    │
    └── New measurement
             │
             ▼
       Garmin Connect
             │
             ▼
       Body Composition
```

The checksum prevents the same measurement from being continuously uploaded every 10 minutes.

---

# Updating the Container

Authentication tokens are stored outside the container.

This means a container upgrade normally does **not** require Wyze or Garmin authentication again.

Update the image with:

```bash
docker compose pull
docker compose up -d --force-recreate
```

Then monitor:

```bash
docker compose logs -f
```

Your existing:

```text
./tokens/wyze_tokens.json
./tokens/garmin_tokens.json
```

will continue to be used.

---

## Historical Backfill

Historical Wyze Scale measurements can be uploaded to Garmin Connect using the `-timewindow` option.

This is useful when:

- Migrating existing Wyze Scale history to Garmin
- Recovering measurements that were not previously synchronized
- Re-uploading measurements from a specific date range

### Usage

Using Docker Compose:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-01-01" "2026-09-30"
```

You can also specify a time:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-01-01 08:00" "2026-01-31 18:00"
```

Supported formats include:

```text
YYYY-MM-DD
YYYY-MM-DD HH:MM
YYYY-MM-DD HH:MM:SS
YYYY-MM-DDTHH:MM
YYYY-MM-DDTHH:MM:SS
```

When only a date is supplied, the start date begins at `00:00:00` and the end date includes the entire day through `23:59:59`.

For example:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-09-01" "2026-09-30"
```

collects all available Wyze measurements from September 1 through September 30, inclusive.

### How Backfill Works

Backfill mode:

1. Authenticates to Wyze using the existing cached token.
2. Retrieves historical scale measurements.
3. Filters measurements to the requested date range.
4. Removes duplicate Wyze records returned during the same run.
5. Sorts measurements from oldest to newest.
6. Authenticates to Garmin once.
7. Uploads each body-composition measurement to Garmin Connect.
8. Prints a summary when complete.

Example output:

```text
========================================================================
Wyze -> Garmin historical synchronization
========================================================================
Start: 2026-09-01T00:00:00-04:00
End:   2026-09-30T23:59:59.999999-04:00

Found 12 measurement(s) in requested time window.

[1/12] 2026-09-02 07:42:18 - 248.2 lb
Uploading: 2026-09-02 07:42:18 - 248.2 lb / 112.58 kg
  -> Garmin upload successful.

[2/12] 2026-09-05 08:11:03 - 247.4 lb
Uploading: 2026-09-05 08:11:03 - 247.4 lb / 112.22 kg
  -> Garmin upload successful.

...

========================================================================
Historical synchronization complete
========================================================================
Measurements found:    12
Successfully uploaded: 12
Failed:                0
========================================================================
```

### Backfill Upload Delay

A delay can be added between historical Garmin uploads to reduce the risk of Garmin API rate limiting.

Add the following environment variable to `docker-compose.yml`:

```yaml
BACKFILL_DELAY_SECONDS: "1.0"
```

Example:

```yaml
environment:

  # Wyze
  WYZE_EMAIL: "your-wyze-email"
  WYZE_PASSWORD: "your-wyze-password"
  WYZE_KEY_ID: "your-wyze-key-id"
  WYZE_API_KEY: "your-wyze-api-key"

  WYZE_TOKEN_FILE: "/wyze_garmin_sync/tokens/wyze_tokens.json"

  # Garmin
  Garmin_username: "your-garmin-email"
  Garmin_password: "your-garmin-password"

  GARMINTOKENS: "/wyze_garmin_sync/tokens"

  # Delay between Garmin uploads during historical backfill
  BACKFILL_DELAY_SECONDS: "1.0"
```

Increase the value if Garmin starts rate limiting a large backfill:

```yaml
BACKFILL_DELAY_SECONDS: "2.0"
```

### Backfill and Cron

Backfill is a **one-time operation**.

When arguments are supplied:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-01-01" "2026-09-30"
```

the container:

```text
starts
  │
  ▼
runs scale.py -timewindow ...
  │
  ▼
uploads historical measurements
  │
  ▼
exits
```

The normal 10-minute cron scheduler is **not started in backfill mode**.

Normal scheduled synchronization continues to be started with:

```bash
docker compose up -d
```

and runs:

```cron
*/10 * * * *
```

Backfill therefore does not interfere with the normal scheduled synchronization.

### Duplicate Warning

`-timewindow` is intended as an explicit historical backfill operation.

The application removes duplicate Wyze records returned during the same backfill run, but it does **not currently query Garmin Connect to determine whether a historical measurement was already uploaded during a previous run**.

Running the same time window multiple times may therefore create duplicate measurements in Garmin Connect.

For example, avoid running this twice unless you intentionally want to re-upload the data:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-01-01" "2026-09-30"
```

---

### Environment Variables

Add the following entry to the existing environment-variable table:

| Variable | Required | Description |
|---|---|---|
| `BACKFILL_DELAY_SECONDS` | No | Delay in seconds between Garmin uploads during historical backfill. Default: `1.0` |

---

### Command Summary

Normal scheduled synchronization:

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f
```

Initial Garmin authentication / MFA:

```bash
docker compose run --rm wyzegarminconnect
```

Historical backfill:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "START_DATE" "END_DATE"
```

Example:

```bash
docker compose run --rm wyzegarminconnect \
  -timewindow "2026-01-01" "2026-09-30"
```


# Troubleshooting

## Wyze: 429 Too Many Requests

Example:

```text
requests.exceptions.HTTPError:
429 Client Error: Too Many Requests
for url:
https://auth-prod.api.wyze.com/api/user/login
```

This means Wyze has rate-limited authentication.

Do not continuously restart the application while this occurs.

Stop the container:

```bash
docker compose down
```

Allow the Wyze authentication rate limit to clear before attempting another initial login.

Once:

```text
wyze_tokens.json
```

exists, scheduled executions should normally display:

```text
Using cached Wyze authentication token.
```

rather than performing another full username/password login.

---

## Garmin Authentication Returns 429

Garmin may return messages similar to:

```text
mobile+cffi returned 429
```

or:

```text
mobile+requests returned 429
```

Garmin can rate-limit authentication based on more than just the source IP address.

The application can skip known-problematic mobile authentication strategies and use alternative Garmin authentication methods.

Do not repeatedly restart the initial authentication process if all available authentication methods are returning 429 responses.

Once:

```text
garmin_tokens.json
```

has been successfully created, normal synchronization should not require the initial Garmin login process again.

---

## Garmin Token Missing

If the normal container reports that interactive Garmin authentication is required:

```bash
docker compose down
```

Then run:

```bash
docker compose run --rm wyzegarminconnect
```

Complete Garmin authentication and MFA.

Verify:

```bash
ls -l tokens/garmin_tokens.json
```

Then restart the service:

```bash
docker compose up -d
```

---

# Upgrading From the Old Garth Version

Previous releases used **Garth** for Garmin authentication.

Old token directories may contain files such as:

```text
oauth1_token.json
oauth2_token.json
```

The current implementation uses:

```text
garmin_tokens.json
```

The old Garth tokens cannot be directly used by the new Garmin authentication implementation.

Perform a new interactive authentication:

```bash
docker compose run --rm wyzegarminconnect
```

Complete Garmin authentication and MFA.

Verify that:

```text
tokens/garmin_tokens.json
```

has been created and that the Garmin upload succeeds.

The obsolete Garth files can then be removed.

---

# Wyze SDK Warning

You may see:

```text
SyntaxWarning: invalid escape sequence '\d'
```

coming from:

```text
wyze_sdk/api/devices/locks.py
```

This warning originates inside the Wyze SDK and does not prevent Wyze Scale synchronization.

---

# Token Security

The token files provide authenticated access to your Wyze and Garmin accounts.

Do not commit them to Git.

Recommended permissions:

```bash
chmod 700 tokens
chmod 600 tokens/*.json
```

Add the following to `.gitignore`:

```gitignore
tokens/
*.fit
cksum.txt
```

You should also avoid committing a `docker-compose.yml` containing real usernames, passwords or API keys.

---

# Repository Layout

The Docker implementation is located in:

```text
Docker files/
```

Important files include:

```text
Docker files/
├── Dockerfile
├── entrypoint.sh
├── fit.py
└── scale.py
```

The repository root contains:

```text
docker-compose.yml
README.md
```

The Docker image uses the Python source files from the `Docker files` directory.

---

# Scheduling

The Docker container runs the synchronization script when the container starts.

It then runs automatically every 10 minutes using cron:

```cron
*/10 * * * * /wyze_garmin_sync/scale.py
```

A separate cron configuration on the Docker host is not required.

---

# Building the Docker Image

Clone the repository:

```bash
git clone https://github.com/svanhoutte/wyze_garmin_sync.git

cd wyze_garmin_sync/"Docker files"
```

Build locally:

```bash
docker build \
  -t svanhoutte/wyzegarminconnect:latest \
  .
```

Or build and push using Buildx:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t svanhoutte/wyzegarminconnect:latest \
  --push \
  .
```

Adjust the target platform as needed for your environment.

---

# Manual Installation

Docker is the recommended installation method.

For a manual Python installation, the primary dependencies include:

```bash
pip install wyze_sdk garminconnect
```

You must provide the same environment variables and persistent token locations used by the Docker container.

For Garmin accounts using MFA, the initial execution must be performed from an interactive terminal.


#### [](https://github.com/svanhoutte/wyze_garmin_sync#run-the-script)Run the script

In your working directory add the execution right on the script 
`chmod +x ./scale.py`  Then run `./scale.py` and if all goes well you should be able to see your data in Garmin connect.
This should be done at least once before setting up the cron as if you have 2FA for Garmin to allow you to enter the 2 step of authentication.

#### [](https://github.com/svanhoutte/wyze_garmin_sync#setup-with-cron)Setup with Cron

Will run the script every 10 min to get if a new measurement has been made on the scale.

    */10 * * * * path_to_script/scale.py 2>&1 | /usr/bin/logger -t garminsync
---

# Credits

This project relies on open-source projects including:

- Wyze SDK
- python-garminconnect

---

# Disclaimer

This project uses unofficial interfaces for Wyze and Garmin Connect.

Changes made by Wyze or Garmin to their APIs or authentication mechanisms may temporarily break synchronization.

This project is not affiliated with Wyze Labs or Garmin.

***
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/sebastienv)
