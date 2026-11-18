# Saraiki Student Council Assistant

Streamlit app for the Saraiki Student Council, Superior University Gold Campus.
Includes sign up / sign in, an AI chat assistant (English, Urdu, Roman Urdu), a team
directory, upcoming events and an About page. Chat is powered by Claude.

## Project structure

```
.
├── app.py               # Streamlit app (pages, chat, navigation)
├── db.py                # Users database + secure password hashing
├── council_data.json    # Founder, purpose, members, roles, phone numbers
├── events.json          # Upcoming events (edit this to add events)
├── knowledge_base.md    # Extra university info and FAQs
├── styles.css           # Ajrak-blue theme
├── .streamlit/config.toml
├── photos/              # (optional) member photos, see below
├── requirements.txt
└── secrets.toml.example
```

## Run locally

```bash
pip install -r requirements.txt
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml   # then add your real API key
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push the project to GitHub (never commit your API key).
2. Go to https://share.streamlit.io -> **Create app** -> choose the repo, branch and `app.py`.
3. **Advanced settings -> Secrets**:
   ```toml
   ANTHROPIC_API_KEY = "your-api-key-here"
   ```
4. Deploy.

## Editing the content

**Phone numbers:** open `council_data.json` and fill `"phone"` for each member
(e.g. `"phone": "+92 300 1234567"`). Get each member's permission first, because
signed-in users and the chatbot will see these numbers.

**Who helps with what:** the `"help_with"` field of each member tells the chatbot whom to
recommend for which problem. Adjust it as needed.

**Events:** add items to `events.json`, commit and push:
```json
[
  {
    "title": "Freshers Welcome Event",
    "date": "2026-12-15",
    "time": "11:00 AM",
    "venue": "Main Auditorium",
    "description": "Welcome session for new students.",
    "contact_role": "Cultural Head"
  }
]
```
Date format is `YYYY-MM-DD`. Past events move to "Past events" automatically, and the chatbot
only talks about upcoming ones.

**Member photos:** save a photo as `photos/<member id>.jpg` (the id is in `council_data.json`,
e.g. `photos/imran-majeed-ahmadani.jpg`). Square photos work best.

## Important notes

- **Accounts storage:** Streamlit Community Cloud resets the local disk on restart/redeploy,
  so `users.db` can be erased and users would need to sign up again. For permanent accounts,
  move `db.py` to a hosted database such as Supabase.
- Passwords are stored salted and hashed (PBKDF2-SHA256), never in plain text.
- A signed-in user is limited to 40 chat messages per session to control API cost.
