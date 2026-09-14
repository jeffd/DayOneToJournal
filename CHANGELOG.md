# Changelog

## 1.1.0-beta.1

Beta build, 2026-09-14. This is the first numbered revision of the original
unversioned importer. The signed download contains the revised source.
Shortcuts runtime and Journal integration checks are pending.

- Preserve the entry body when a title is generated.
- Clear location fields between entries so an entry without location data does
  not inherit the previous entry's location.
- Exclude ledger files from export selection and ask which Day One JSON to use.
- Check every entry's UUID instead of skipping entries by ledger count.
- Allow an existing ledger in another folder, and save progress back to that
  folder. This lets reduced exports share the original ledger.
- Stop when no export JSON is available, the selected export has no entries, or
  an entry has no UUID.
- Load the ledger once, cache the exported file list, and clear repeat outputs instead of
  accumulating them across the import.
- Add editable shortcut source and 12 offline regression checks.

The offline checks pass, as do plist lint and static validation for macOS 27.
These checks do not run Shortcuts, AI actions, or Journal. They do not establish
that the reported large-archive crash is fixed or verify iPhone compatibility.
The AI actions, Journal creation action, and 10-second delay remain in place.

The separate export-preparation helper is not part of this version. Its source
path protection still needs work before distribution.
