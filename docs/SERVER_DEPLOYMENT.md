# Server deployment preparation

The repository now includes a Docker image and a persistent named volume for the encrypted simulation ledger. This prepares a single-host deployment; it does not deploy the app or create hosting-provider secrets.

## Before starting

1. Provision a trusted server with Docker Engine and Docker Compose.
2. Restrict inbound access to port 8501 behind HTTPS reverse proxy/authentication; do not expose the app publicly without access control.
3. Create a Fernet key in a trusted terminal:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
4. Copy `.env.example` to `.env` on the server only and replace the placeholder with the generated key.
5. Ensure `.env` is excluded from source control. Do not paste the key into GitHub, issues, or chat.
6. Start with `docker compose up -d --build`.
7. Verify the application health endpoint and that the investment page reports encrypted persistence enabled.
8. Back up the named volume and key separately. Run a restore drill using `nexus.ledger_backup`.

## Important limits

- This deployment stores only simulated balances and virtual withdrawals.
- A single-host Docker volume is not high availability, distributed locking, or a managed database.
- If multiple hosts or containers must write to one ledger, use a database designed for transactions and distributed coordination; do not share this file-based ledger over an arbitrary network filesystem.
- Keep the key in a hosting secret manager in managed environments; the local `.env` method is only for a private single-host setup.
- Real money, custody, real withdrawals and live orders remain disabled pending independent security, legal and operational review.
