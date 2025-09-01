# RaffleFleet

Full source code for [**RaffleFleet**](https://x.com/RaffleFleet), a CLI program for automating large amounts of online raffle entries for limited-edition items (mostly sneakers) through HTTP requests. Developed from 2022–2023, with ~150 bèta users at its peak.

## [API](/api)
REST API build with Flask that was hosted on AWS Lambda. Features:
- User authentication through [Whop](https://whop.com)'s API.
- Updating user analytics (raffle entries, wins, etc.) in our DynamoDB database.
- Sending user logs to the admin Discord WebHook for debugging purposes.

## [App](/app)
Python CLI app with logic for entering raffles on ~20 e-commerce websites. Features:
- Custom TLS client for HTTP requests.
- Automatic app updater when newer versions are available.
- Automatic CAPTCHA solving through 3rd parties.
- Automatic creditcard payments, including 3D Secure handling.
- Automatic email verification through IMAP.
- Address generator (Geocoding) with Mapbox.
- iCloud HME (Hide My Email) address generator.

## License
[MIT license](/LICENSE.txt)
