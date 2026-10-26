# Aram Zone timers

Posts the Aram Zone Halloween event ads in Discord every 3 hours through webhooks.
Each channel only ever holds the newest copy, and each ad stops on its own when its event starts.

- `post.py` holds the posts and their end times.
- The webhook links are GitHub secrets, never in this repo.
- `state.json` remembers the last copy in each channel, so the next run can replace it.
