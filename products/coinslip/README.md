# CoinSlip

A privacy-first, browser-only USDT invoice formatter. It creates a printable invoice and a JSON record; it does **not** custody funds, verify transfers, or act as a payment processor.

## Current features

- USDT invoices for BNB Smart Chain (BEP20) and Ethereum (ERC20)
- Client-side preview, print / Save as PDF, and JSON export
- Optional local draft saving (browser storage only)
- Basic EVM address validation and USDT amount precision up to 6 decimal places
- CSV export for spreadsheet workflows
- One-click copy of payment instructions with an explicit unverified-payment warning
- No accounts, API keys, wallet connection, or private-key collection

## Run locally

Open `index.html` in a modern browser. No build step or server is required.

## Publish as a static site

The app is a static HTML file and can be hosted on any static-site host. The repository includes a GitHub Actions smoke-check workflow. A successful check does not itself publish the site; GitHub Pages must be enabled for the repository and configured to deploy the selected branch or workflow.

## Safety and limitations

- An EVM address format check cannot prove that an address belongs to the intended person.
- The invoice does not check on-chain payments. Never mark an invoice paid based only on a screenshot or message.
- The sender must select the exact network shown on the invoice.
- Drafts are stored unencrypted in the current browser profile. Do not save sensitive customer data on a shared device.
- CoinSlip is not affiliated with Tether or any wallet provider.

## Quality checks

Run:

```bash
python products/coinslip/tests/validate.py
```

The check uses Python's standard library and Node.js only.
