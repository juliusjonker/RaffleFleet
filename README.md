# RaffleFleet

Full source code for [**RaffleFleet**](https://x.com/RaffleFleet), a CLI program for automating large amounts of online raffle entries for limited-edition items (mostly sneakers). Developed from 2022–2023, with ~120 bèta users at peak.

## Repository Structure
- **/api**: REST API for authentication through Whop and interactions with the DynamoDB database, hosted on AWS Lambda.
- **/app**: CLI app with logic for entering raffles on ~20 e-commerce websites. Includes automating creditcard payments, solving CAPTCHA challenges, handling email verification through IMAP, and much more.
