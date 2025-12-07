# Getting Slack Credentials from Browser

This guide walks you through extracting your Slack token and cookie from your browser. These credentials let the agent act as you in Slack.

## Quick Method: JavaScript Console

The fastest way to get your credentials:

### Step 1: Open Slack in Browser
Go to `https://your-workspace.slack.com` in your browser (not the desktop app)

### Step 2: Open Developer Console
- Press `F12` or `Ctrl+Shift+J` (Windows/Linux) or `Cmd+Option+J` (Mac)
- Click the **Console** tab

### Step 3: Get Token

```javascript
JSON.parse(localStorage.localConfig_v2).teams[document.location.pathname.match(/client\/([A-Z0-9]+)/)[1]].token
```

### Step 4: Get Cookie

```javascript
document.cookie.match(/d=(xoxd-[^;]+)/)[1]
```

Copy both values and set as environment variables:

```bash
export SLACK_TOKEN="xoxc-..."
export SLACK_COOKIE="xoxd-..."
```

---

## Manual Method (If Script Doesn't Work)

If the JavaScript method doesn't find your credentials, use this manual approach:

## Prerequisites

- Access to your Slack workspace
- A modern browser (Chrome, Firefox, Edge, Safari)

## Step-by-Step Instructions

### Step 1: Open Slack in Your Browser

1. Go to your Slack workspace URL: `https://your-workspace.slack.com`
2. **Important**: Use your browser, NOT the Slack desktop app
3. Sign in if prompted

### Step 2: Open Developer Tools

**Chrome / Edge:**
- Press `F12` or `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Option+I` (Mac)
- Or: Right-click anywhere → "Inspect"

**Firefox:**
- Press `F12` or `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Option+I` (Mac)
- Or: Right-click anywhere → "Inspect"

**Safari:**
- First enable: Safari → Preferences → Advanced → "Show Develop menu"
- Then: `Cmd+Option+I` or Develop → Show Web Inspector

### Step 3: Go to the Network Tab

1. Click the **Network** tab in Developer Tools
2. If it's empty, refresh the page (`F5` or `Ctrl+R`)

![Network Tab](https://i.imgur.com/placeholder.png)

### Step 4: Filter for API Requests

1. In the filter/search box, type: `api`
2. You should see requests like:
   - `client.counts`
   - `client.boot`
   - `conversations.list`
   - `users.list`

3. Click on any of these requests

### Step 5: Find the Cookie Value

1. With a request selected, look at the **Headers** tab (right panel)
2. Scroll down to **Request Headers**
3. Find the `cookie` header
4. Look for the value that starts with `d=xoxd-`

**Example cookie header:**
```
cookie: d=xoxd-ABC123DEF456...; d-s=1234567890; ...
```

5. **Copy only the `xoxd-...` part** (everything after `d=` until the next `;`)

**Your cookie looks like:**
```
xoxd-ABC123DEF456GHI789JKL012MNO345PQR678STU901VWX234YZA567BCD890...
```

### Step 6: Find the Token Value

**Method A: From Request Payload**

1. With the same request selected, click the **Payload** tab (or "Request" tab in Firefox)
2. Look for `token` in the form data
3. Copy the value starting with `xoxc-`

**Method B: From Request Headers**

1. In the **Headers** tab, look for `Authorization` header
2. It may contain: `Bearer xoxc-...`
3. Copy the token value

**Your token looks like:**
```
xoxc-1234567890123-1234567890123-1234567890123-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab
```

### Step 7: Verify Your Credentials

Your credentials should look like:

| Credential | Format | Example |
|------------|--------|---------|
| Token | `xoxc-NUMBERS-NUMBERS-NUMBERS-64HEXCHARS` | `xoxc-123-456-789-abcd...` |
| Cookie | `xoxd-ALPHANUMERIC...` | `xoxd-ABC123...` |

## Visual Guide (Chrome)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🔍 Elements  Console  Sources  [Network]  Performance  Memory  ...     │
├─────────────────────────────────────────────────────────────────────────┤
│ Filter: [api____________]  □ Preserve log  □ Disable cache             │
├─────────────────────────────────────────────────────────────────────────┤
│ Name              Status  Type   Size    Time                           │
│ ─────────────────────────────────────────                               │
│ client.counts     200     fetch  1.2 KB  45 ms   ◄── Click this        │
│ conversations...  200     fetch  4.5 KB  120 ms                        │
│ users.list        200     fetch  2.1 KB  89 ms                         │
├─────────────────────────────────────────────────────────────────────────┤
│ [Headers]  Preview  Response  Timing                                    │
│                                                                         │
│ ▼ Request Headers                                                       │
│   cookie: d=xoxd-ABC123...; d-s=1699999999   ◄── Copy xoxd-... value   │
│   authorization: Bearer xoxc-123-456-789-abc ◄── Or find token here    │
│                                                                         │
│ [Payload]  ◄── Click for token                                         │
│   token: xoxc-123-456-789-abcdef...          ◄── Copy this value       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Using the Credentials

### Option 1: Environment Variables (Recommended)

```bash
export SLACK_TOKEN="xoxc-your-token-here"
export SLACK_COOKIE="xoxd-your-cookie-here"

uv run python -m agentic_curator
```

### Option 2: Interactive Input

```bash
uv run python -m agentic_curator

# You'll be prompted:
# Slack token (xoxc-...): <paste your token>
# Slack cookie (xoxd-...): <paste your cookie>
```

### Option 3: .env File

Create a `.env` file in the project root:

```bash
SLACK_TOKEN=xoxc-your-token-here
SLACK_COOKIE=xoxd-your-cookie-here
```

Then run:
```bash
source .env  # or use python-dotenv
uv run python -m agentic_curator
```

## Troubleshooting

### "I can't find the cookie header"

1. Make sure you're in the **Network** tab
2. Refresh the page to capture new requests
3. Make sure you clicked on an actual API request (starts with `client.` or `conversations.` etc.)

### "I can't find the token"

1. Try the **Payload** tab instead of Headers
2. Look for form data with `token` field
3. If using "Fetch/XHR" filter, the token might be in the request body

### "My token doesn't start with xoxc-"

- `xoxc-` = Client token (what we need)
- `xoxb-` = Bot token (from Slack apps)
- `xoxp-` = User OAuth token

If you see `xoxb-` or `xoxp-`, you might be looking at the wrong request or have a Slack app installed. Look for requests that use `xoxc-` tokens.

### "The credentials stopped working"

Slack session cookies expire. If you get authentication errors:
1. Open Slack in browser again
2. Extract fresh credentials
3. Update your environment variables

### "I'm getting rate limited"

Slack has API rate limits. If you see `ratelimited` errors:
1. Increase poll interval: `--poll-interval 10`
2. Wait a few minutes before retrying

## Security Notes

⚠️ **Keep your credentials secure!**

- These credentials give full access to your Slack account
- Never commit them to git (add `.env` to `.gitignore`)
- Don't share them with others
- They can be used to read/send messages as you

The agent uses these credentials to:
- Read messages in channels you're in
- Post messages as you
- Access your DMs
