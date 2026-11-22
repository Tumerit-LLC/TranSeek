# TranSeek

TranSeek is a macOS 15 or later app for navigating on-screen text and controls with your keyboard. Its optional browser extension connects to the Mac app to identify interactive webpage controls.

- [TranSeek website](https://transeekmac.com/)
- [Releases and installer downloads](https://github.com/Tumerit-LLC/TranSeek/releases)
- [Support](https://transeekmac.com/support)
- [Privacy policy](https://transeekmac.com/privacy)

Use the installer linked in the release notes for manual installation. Sparkle uses the separate update ZIP.

For a bug report, include your macOS version, TranSeek version, steps to reproduce, and browser and extension versions if relevant. Use [TranSeek Support](https://transeekmac.com/support) for purchases, activation, and other private account details.

## Release notes localization

Write release notes in English in the GitHub release. Publish the signed Sparkle archive and appcast with a matching enclosure for the release tag. Run **Localize Sparkle release notes** from Actions with that tag to generate a localized appcast artifact. The workflow uses the same Google Cloud Translation API and language set as Tethered. Configure the repository Actions secret `GOOGLE_TRANSLATE_API_KEY` with a key restricted to the Cloud Translation API.

Download and review the artifact before publishing it to the website. If the feed is signed, sign the final localized bytes before deploying them. The workflow leaves publication and signing to the release operator.
