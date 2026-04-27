# WhiskyWise — Home Assistant Add-on

Your personal spirits guide, running natively inside Home Assistant.

## Installation

1. Go to **Settings → Add-ons → Add-on Store**.
2. Click the ⋮ menu (top-right) and select **Repositories**.
3. Add: `https://github.com/prolife86/WhiskyWise`
4. Find **WhiskyWise** in the store and click **Install**.

## Configuration

| Option | Required | Description |
|---|---|---|
| `secret_key` | ✅ | Flask session secret — **must be changed** |

```yaml
secret_key: "your-long-random-secret-here"
```

> ⚠️ Always set a strong `secret_key` before first use.

## Access

After starting the add-on, open the Web UI via the **Open Web UI** button,
or navigate to `http://homeassistant.local:5000`.

## Default Credentials

- **Username:** `admin`
- **Password:** `whiskywise`

> Change your password immediately via ⚙️ Settings → Change Password.

## Data Persistence

All data is stored in the add-on's `/data` directory, which Home Assistant
maps to a persistent volume. Your collection and photos survive restarts and
updates.

- Database: `/data/db/whiskywise.db`
- Photos: `/data/uploads/`

## Support

- [GitHub Issues](https://github.com/prolife86/WhiskyWise/issues)
- [Repository](https://github.com/prolife86/WhiskyWise)
