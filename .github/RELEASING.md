# TranSeek releases

Write release notes in English. Attach the installer DMG, the signed Sparkle ZIP, and its matching `.edSignature` sidecar to the GitHub release before publishing. Use exactly one Sparkle ZIP per tag and give new updates a build number higher than the current feed. The production app reads the signed feed at `https://transeekmac.com/appcast.xml`.

Publishing or editing a release runs **Localize Sparkle release notes**. You can also dispatch it manually for a tag. The workflow verifies the archive against TranSeek’s Sparkle public key, reads the checked-in copy of the signed production feed, adds the update, and translates the release notes. It uses the repository Actions secret `GOOGLE_TRANSLATE_API_KEY`. The resulting `localized-appcast` artifact contains the complete updated XML.

Download and review the artifact. On the release Mac, run `sign_update --account com.Tumerit.Transeek appcast.xml` and verify it with `sign_update --account com.Tumerit.Transeek --verify appcast.xml`. Publish the verified file to the existing website feed URL and commit the same signed bytes as `appcast.xml` in this repository. Keep the two copies in sync so the workflow can retain the previous updates without fetching the production website. The private key stays in the release Mac’s Keychain.

If the checked-in feed already has an entry for the tag, the workflow can refresh its notes when the archive URL, build, length, and signature match. A mismatched entry fails verification. Use a new version and higher build number for a replacement public update.
