# WhiskyWise

Your personal spirits guide, running natively inside Home Assistant.

## Installation

1. Go to **Settings → Add-ons**
2. Click **⋮** (top-right) → **Repositories**
3. Paste in the repository URL and click **Add**:
   ```
   https://github.com/prolife86/WhiskyWise
   ```
4. Find **WhiskyWise** in the add-on list and click **Install**
5. Go to the **Configuration** tab and set your `secret_key`
6. Go to the **Info** tab and click **Start**

## Configuration

| Option | Required | Description |
|---|---|---|
| `secret_key` | ✅ | Flask session secret — **must be changed before first use** |

```yaml
secret_key: "your-long-random-secret-here"
```

## Access

After starting the add-on, click **Open Web UI** on the Info tab, or navigate to `http://homeassistant.local:5000`.

## Default Credentials

- **Username:** `admin`
- **Password:** `whiskywise`

> ⚠️ Change your password immediately via ⚙️ Settings → Change Password inside WhiskyWise.

## Data Persistence

All data is stored in the add-on's `/data` directory and survives restarts and updates.

- Database: `/data/db/whiskywise.db`
- Photos: `/data/uploads/`

Back up your data using the standard Home Assistant backup system.
