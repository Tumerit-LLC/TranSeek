# TranSeek releases

Write release notes in English. Attach the signed Sparkle ZIP, its matching signed `appcast.xml`, and the installer DMG before publishing the GitHub release. The production app reads the signed feed from `https://transeekmac.com/appcast.xml`.

Publishing or editing a release runs **Localize Sparkle release notes**. You can also dispatch it manually for a tag. The workflow uses the same Google Cloud Translation API and language set as Tethered. Configure the repository Actions secret `GOOGLE_TRANSLATE_API_KEY` with a key restricted to the Cloud Translation API.

Download and review the localized appcast artifact. On the release Mac, run `sign_update --account com.Tumerit.Transeek appcast.xml` and verify it with `sign_update --account com.Tumerit.Transeek --verify appcast.xml`. Then publish the signed file to the website. The Sparkle private key stays in the release Mac’s Keychain.
