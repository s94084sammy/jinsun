# Security

## Do not commit

These files must stay on the home PC:

1. `.env` and `data/.env`
2. `data/auth.json` (model login)
3. `data/jinsun/.google-email` and `data/jinsun/.google-pass`
4. Cloudflare tunnel token `JINSUN_TUNNEL_TOKEN`
5. LINE channel access token and channel secret
6. CWA / TDX / MoENV keys
7. Chrome profiles under `data/`

`overlay/env.example` is the public template. Copy it. Never commit the filled copy.

## Report a vulnerability

Open a private GitHub security advisory on this repository. Do not file a public issue that contains tokens, LINE user IDs, or household data.

## Defaults that matter

1. LINE allowlist: only `LINE_ALLOWED_USERS` is answered. Leave `LINE_ALLOW_ALL_USERS=false`.
2. Push is off. Reply tokens are free; Push is metered.
3. Inbound gate blocks transfers, OTPs, unknown downloads, remote desktop, and prize-fee scams before the model.
4. Browser fill refuses bank, National Health Insurance, household registration, and payment pages.
5. Do not change system or account passwords as part of using Jinsun.
6. Do not put API keys in frontend code, chat logs, or this public repository.
