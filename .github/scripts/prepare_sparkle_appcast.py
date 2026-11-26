import base64
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path


APPCAST = Path("appcast.xml")
PUBLIC_KEY = "0oRHkHBWGW73sTwr5ILQjOLmF+28kLsrEzOxPUdP+cI="
FEED_URL = "https://transeekmac.com/appcast.xml"
BUNDLE_ID = "com.Tumerit.Transeek"
SPARKLE = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"


def request(url, token):
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "transeek-sparkle-appcast", "Accept": "application/vnd.github+json"}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


def download(asset, destination):
    with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if destination.stat().st_size != asset["size"]:
        raise ValueError(f"Size mismatch for {asset['name']}")
    digest = asset.get("digest")
    if digest:
        actual = "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"Digest mismatch for {asset['name']}")


def one_asset(assets, name):
    matches = [asset for asset in assets if asset["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one release asset named {name}, found {len(matches)}")
    return matches[0]


def bundle_info(archive):
    with zipfile.ZipFile(archive) as zipped:
        matches = [name for name in zipped.namelist() if name == "TranSeek.app/Contents/Info.plist"]
        if len(matches) != 1:
            raise ValueError("Expected TranSeek.app/Contents/Info.plist in the Sparkle ZIP")
        return plistlib.loads(zipped.read(matches[0]))


def prepare(tag, repository, token, resync_archive=False):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a semantic release tag such as v0.9.3")
    encoded_tag = urllib.parse.quote(tag, safe="")
    with request(f"https://api.github.com/repos/{repository}/releases/tags/{encoded_tag}", token) as response:
        release = json.load(response)
    if release["draft"] or release["tag_name"] != tag:
        raise ValueError("Expected a published release with the requested tag")

    version = tag[1:]
    archive_pattern = re.compile(rf"TranSeek-{re.escape(version)}(?:-[0-9]+(?:-r[0-9]+)?)?\.Sparkle\.zip")
    archives = [asset for asset in release["assets"] if archive_pattern.fullmatch(asset["name"])]
    if len(archives) != 1:
        raise ValueError("Expected exactly one TranSeek Sparkle ZIP for this tag")
    archive_asset = archives[0]
    archive_name = archive_asset["name"]
    signature_asset = one_asset(release["assets"], archive_name + ".edSignature")

    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / archive_name
        sidecar = Path(directory) / signature_asset["name"]
        download(archive_asset, archive)
        download(signature_asset, sidecar)
        signature = sidecar.read_text(encoding="ascii").strip()
        attributes = re.fullmatch(r'sparkle:edSignature="([A-Za-z0-9+/]{86}==)"\s+length="([0-9]+)"', signature)
        if attributes:
            signature = attributes.group(1)
            if int(attributes.group(2)) != archive_asset["size"]:
                raise ValueError("The Sparkle signature asset has the wrong archive length")
        if len(base64.b64decode(signature, validate=True)) != 64:
            raise ValueError("The Sparkle signature asset is not a valid Ed25519 signature")
        info = bundle_info(archive)
        expected = {"CFBundleShortVersionString": version, "CFBundleIdentifier": BUNDLE_ID, "SUPublicEDKey": PUBLIC_KEY}
        for key, value in expected.items():
            if info.get(key) != value:
                raise ValueError(f"Unexpected {key} in Sparkle ZIP")
        if info.get("SUFeedURL") != FEED_URL:
            raise ValueError("Unexpected SUFeedURL in Sparkle ZIP")
        build = str(info.get("CFBundleVersion", ""))
        if not build.isdecimal():
            raise ValueError("Expected a numeric CFBundleVersion")
        subprocess.run(["swift", ".github/scripts/verify_sparkle_signature.swift", PUBLIC_KEY, signature, str(archive)], check=True)

        with zipfile.ZipFile(archive) as zipped:
            executable = Path(directory) / "TranSeek"
            executable.write_bytes(zipped.read("TranSeek.app/Contents/MacOS/TranSeek"))
        architectures = subprocess.check_output(["lipo", "-archs", str(executable)], text=True).split()
        if architectures != ["arm64"]:
            raise ValueError("Expected an arm64 TranSeek executable")

    source = APPCAST.read_text(encoding="utf-8")
    updated = update_feed(source, release, archive_asset, info, signature, resync_archive)
    APPCAST.write_text(updated, encoding="utf-8")


def update_feed(source, release, archive_asset, info, signature, resync_archive=False):
    tag = release["tag_name"]
    build = str(info["CFBundleVersion"])
    root = ET.fromstring(source)
    items = root.findall("./channel/item")
    matching = []
    for item in items:
        enclosure = item.find("enclosure")
        if enclosure is not None and f"/releases/download/{tag}/" in urllib.parse.urlsplit(enclosure.get("url", "")).path:
            matching.append(item)
    if matching:
        if len(matching) != 1:
            raise ValueError("Multiple appcast items match the release tag")
        item = matching[0]
        enclosure = item.find("enclosure")
        if item.findtext(SPARKLE + "version") != build or enclosure.get("url") != archive_asset["browser_download_url"]:
            raise ValueError("Existing appcast item does not match the release build or URL")
        if enclosure.get(SPARKLE + "edSignature") == signature and enclosure.get("length") == str(archive_asset["size"]):
            return source
        if not resync_archive or item.findtext(SPARKLE + "minimumSystemVersion") != info.get("LSMinimumSystemVersion"):
            raise ValueError("Existing appcast item does not match the release archive")
        url = archive_asset["browser_download_url"]
        enclosures = list(re.finditer(r"<enclosure\b[^>]*>", source))
        matches = [match for match in enclosures if f'url="{url}"' in match.group()]
        if len(matches) != 1:
            raise ValueError("Cannot locate the existing enclosure in the checked-in appcast")
        match = matches[0]
        entry = re.sub(r'sparkle:edSignature="[^"]+"', f'sparkle:edSignature="{signature}"', match.group())
        entry = re.sub(r'\blength="[0-9]+"', f'length="{archive_asset["size"]}"', entry)
        updated = source[:match.start()] + entry + source[match.end():]
        ET.fromstring(updated)
        return updated

    existing_builds = [int(item.findtext(SPARKLE + "version")) for item in items]
    if existing_builds and int(build) <= max(existing_builds):
        raise ValueError("The release build must be newer than existing appcast items")
    published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Expected an RSS channel in the checked-in appcast")
    minimum = info.get("LSMinimumSystemVersion")
    if not isinstance(minimum, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", minimum):
        raise ValueError("Expected LSMinimumSystemVersion in the Sparkle ZIP")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = f"TranSeek {tag[1:]}"
    ET.SubElement(item, "pubDate").text = format_datetime(published)
    ET.SubElement(item, SPARKLE + "version").text = build
    ET.SubElement(item, SPARKLE + "shortVersionString").text = tag[1:]
    ET.SubElement(item, SPARKLE + "minimumSystemVersion").text = minimum
    ET.SubElement(item, SPARKLE + "hardwareRequirements").text = "arm64"
    ET.SubElement(item, "enclosure", {
        "url": archive_asset["browser_download_url"],
        "length": str(archive_asset["size"]),
        "type": "application/octet-stream",
        SPARKLE + "edSignature": signature,
    })
    ET.register_namespace("sparkle", SPARKLE[1:-1])
    ET.indent(item, space="    ")
    entry = ET.tostring(item, encoding="unicode").replace(' xmlns:sparkle="' + SPARKLE[1:-1] + '"', '', 1)
    first_item = re.search(r"(?m)^([ \t]*)<item>", source)
    channel_end = re.search(r"(?m)^([ \t]*)</channel>", source)
    if first_item:
        position, indent = first_item.start(), first_item[1]
    elif not items and channel_end:
        position, indent = channel_end.start(), channel_end[1] + "    "
    else:
        raise ValueError("Cannot locate the insertion point in the checked-in appcast")
    updated = source[:position] + "".join(indent + line + "\n" for line in entry.splitlines()) + source[position:]
    ET.fromstring(updated)
    return updated


if __name__ == "__main__":
    prepare(sys.argv[1], os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"], os.environ.get("RESYNC_ARCHIVE") == "true")
