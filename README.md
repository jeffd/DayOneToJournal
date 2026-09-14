# Day One to Journal Importer

Import Day One JSON exports into Apple's Journal app with a Shortcut for iOS 26
and macOS 26.

This Shortcut was built to move a large Day One archive into Journal while
working around a few current Shortcuts and Journal limitations. It has been used
to move more than 1,200 entries, and other users have reported successful
imports with much larger archives.

## Version and downloads

The revised source is **1.1.0-beta.1**, an unreleased update to the original
unversioned importer. See [the changelog](CHANGELOG.md) for its fixes and test
status.

The `.shortcut` below is the older signed importer. It does **not** contain the
1.1.0-beta.1 fixes. A signed beta download is pending.

- [Older signed importer](Import_Day_One_to_Journal.shortcut)
- Original discussion: [Day One to Journal Importer Shortcut for iOS & macOS 26](https://www.reddit.com/r/appleJournal/comments/1mxwdey/day_one_to_journal_importer_shortcut_for_ios/)

## What it imports

- Entry text from Day One JSON exports.
- Entry dates, converted to the relevant date and timezone when location data is
  available.
- Photos, up to Journal's per-entry attachment limit.
- Generated titles for entries that do not already have one.
- A weather summary appended to the bottom of the entry, since Journal import
  actions do not currently support Day One weather metadata directly.
- Day One location details appended to the entry text so you can manually add
  the location back in Journal later.

The Shortcut also keeps a JSON ledger of entries it has already imported. It
checks each entry's UUID rather than skipping entries by their position in the
export. Keep using the same ledger when resuming or importing reduced batches.
If Journal creates an entry but the ledger cannot be saved afterward, a retry
can still duplicate that entry.

## Requirements

- iOS 26 or macOS 26.
- Apple's Journal app.
- A Day One export in JSON format.
- Apple Intelligence, ChatGPT, or another model configured for the Shortcut's
  AI actions, unless you customize the Shortcut to remove those steps.

The Shortcut can run on macOS even if the Journal actions do not appear as
standalone options in Shortcuts.

## Export from Day One

These steps describe the revised 1.1.0-beta.1 source. The older signed download
does not include the ledger-folder menu or JSON selection step.

1. Export your Day One journal as JSON.
2. Day One will create a zip archive.
3. Unzip the archive.
4. Run the Shortcut and select the unzipped export folder.
5. Choose **Use export folder** to load or create `already_imported_uuids.json`
   there. To resume with a ledger stored elsewhere, choose **Choose existing
   ledger folder** and select the folder containing that file.
6. Choose the Day One JSON file from the list. Ledger files are excluded.

The Shortcut saves progress back to the chosen ledger folder. The existing-ledger
option stops if that folder does not contain `already_imported_uuids.json`.

Run the Shortcut against the unzipped folder itself. That gives it access to the
JSON files and the media files referenced by those JSON entries.

## Import notes

Large imports can take a long time. With thousands of entries, the Shortcuts
progress indicator may appear stuck while it is still working.

Shortcuts may occasionally fail with an error like:

> This action is trying to share 10315055452202434010 Finder items, which is not allowed.
> You can allow this in Settings.

If that happens, quit Shortcuts, reopen it, and run the importer again. The
ledger file lets the Shortcut continue from entries it has not imported yet.

Journal may also drop entries if they are sent too quickly, so the Shortcut is
designed to be run more than once. For very large libraries, expect to restart
and resume the import multiple times.

## Known limitations

- Audio files are not imported.
- Videos are not imported.
- Day One sub-journals cannot be assigned automatically by the Shortcut. Import
  smaller journals first if you want easier manual cleanup in Journal.
- Journal locations cannot be set directly by the Shortcut, so Day One location
  details are appended to the entry text instead.
- Entries with more photos than Journal allows will be limited by Journal's
  per-entry attachment cap.
- The title and weather steps use AI actions. Older devices without Apple
  Intelligence support, unsupported Siri languages, or model/content issues may
  cause those steps to fail.

## Customization tips

The Shortcut intentionally leaves some variables in place even when they are not
used by the default flow, so it is easier to customize.

Useful changes people have made or discussed:

- Remove the AI title generation step and use a blank or temporary title when
  Day One entries do not have one.
- Remove the weather summary step if you do not want extra text appended to
  entries.
- Switch the AI actions to ChatGPT or another model if Apple's model struggles
  with the entry content or language.
- Temporarily change your Siri language to one supported by Apple Intelligence
  if language support appears to be the issue.
- Add audio or video support by matching the media URLs in Day One's JSON export
  to the corresponding exported files, similar to how photos are handled.

## Debugging tips

If entry text is missing, truncated, or only imports up to the first paragraph
break, add a Shortcuts "Show Content" action around the `text` or
`EntryWithoutPhotos` value to inspect what the Shortcut is passing into Journal.

If titles look wrong, add an alert or "Show Content" action around the title
extraction step and confirm whether the generated title is what you expect.

If you see a path error, make sure the Shortcut is being run on the unzipped Day
One export folder and that every file it reads is inside that selected folder.

## Contributing

Patches are welcome. The Shortcut is intended to be open and editable so people
can adapt it to their own export shape, AI model, and Journal cleanup workflow.

The editable plist is in
[`shortcuts/Import_Day_One_to_Journal.xml`](shortcuts/Import_Day_One_to_Journal.xml).
The root `.shortcut` still contains the older signed version. After editing,
validate and sign the plist before replacing that download. Do not run the
importer against a personal Journal to test it.

Run the offline regression checks with:

```sh
python3 -m unittest discover -s tests -v
```

These checks evaluate selected plist fragments with synthetic data and in-memory
file operations. Unsupported actions, including Journal, are rejected. They
cover JSON selection, UUID-based resume, ledger routing, and per-entry text and
location state. They do not verify Apple's Shortcuts runtime, AI responses,
iPhone compatibility, or Journal persistence.
