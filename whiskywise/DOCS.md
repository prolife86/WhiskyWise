# Home Assistant Add-on: WhiskyWise

WhiskyWise is a self-hosted personal spirits guide. It lets you track your
whisky collection, log detailed tasting notes, visualise flavour profiles with
a radar chart, manage a wishlist, and export your data to CSV — all running
locally inside Home Assistant with no cloud dependency.

## Installation

The installation of this add-on is straightforward and not different in
comparison to installing any other Home Assistant add-on.

1. Go to **Settings → Add-ons** in your Home Assistant instance.

1. Click **⋮** (top-right) → **Repositories** and add the following URL:

   ```
   https://github.com/prolife86/WhiskyWise
   ```

1. Find the **WhiskyWise** add-on in the list and click **Install**.

1. Go to the **Configuration** tab and set a strong `secret_key`.

1. Go to the **Info** tab and click **Start**.

1. Check the **Log** tab to verify everything started correctly.

1. Click **Open Web UI** to open WhiskyWise.

## First-time login

The default credentials are:

- **Username:** `admin`
- **Password:** `whiskywise`

> ⚠️ Change your password immediately after first login via
> **⚙️ Settings → Change Password** inside WhiskyWise.

## Configuration

| Option | Required | Description |
|---|---|---|
| `secret_key` | ✅ | Flask session secret. Must be a long random string. Sessions will not persist across restarts if this is not set. |

Example configuration:

```yaml
secret_key: "your-long-random-secret-here"
```

## Data persistence

All data is stored in the add-on's `/data` directory, which Home Assistant
maps to a persistent volume automatically. Your collection, tasting notes,
and photos survive add-on restarts and updates.

- Database: `/data/db/whiskywise.db`
- Photos: `/data/uploads/`

Back up your data using the standard Home Assistant backup system.

## Changelog & Releases

This repository keeps a change log using [GitHub's releases][releases]
functionality. The format of the log is based on
[Keep a Changelog][keepchangelog].

Releases are based on [Semantic Versioning][semver], and use the format
of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented
based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bugfixes and package updates.

## Support

Got questions?

You have several options to get them answered:

- [Open an issue][issue] on GitHub.
- The Home Assistant [Community Forum][forum].
- The [Reddit subreddit][reddit] at [/r/homeassistant][reddit].

## Authors & contributors

WhiskyWise is created and maintained by [prolife86][prolife86].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

MIT License

Copyright (c) 2026 prolife86

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[contributors]: https://github.com/prolife86/WhiskyWise/graphs/contributors
[forum]: https://community.home-assistant.io
[issue]: https://github.com/prolife86/WhiskyWise/issues
[keepchangelog]: https://keepachangelog.com/en/1.1.0/
[prolife86]: https://github.com/prolife86
[reddit]: https://reddit.com/r/homeassistant
[releases]: https://github.com/prolife86/WhiskyWise/releases
[semver]: https://semver.org/spec/v2.0.0.html
