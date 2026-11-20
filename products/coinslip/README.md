# CoinSlip — USDT Invoice Maker

A lightweight, mobile-friendly invoice creator for freelancers and small businesses that accept USDT.

## What it does
- Creates a printable invoice and a downloadable JSON record.
- Supports BNB Smart Chain (BEP20) and Ethereum (ERC20) labels.
- Validates the recipient's EVM address format and amount.
- Runs entirely in the browser; no account, backend, analytics, wallet connection, or private keys.
- Keeps payment status explicitly **unverified**. It does not claim to detect or confirm transfers.

## Run locally
Open `index.html` in any modern browser. No build step or dependencies.

## Safety
CoinSlip is not a wallet or payment processor. It never receives funds or asks for seed phrases. Always verify the token contract, network, recipient address, and transaction independently. A valid-looking address does not prove ownership or payment.

## Product status
MVP prototype. Not yet deployed, monetized, or connected to an automated payment-verification service. No revenue is claimed.

## License
MIT
