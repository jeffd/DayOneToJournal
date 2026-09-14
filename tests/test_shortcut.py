"""Offline regression checks against the actual plist, never the Shortcuts runtime.

The small evaluator only models the actions used by the tested fragments.
Files, dialogs, and model responses are in-memory fixtures. Unsupported actions
(including Journal and Run Shortcut) fail closed. This does not test Apple coercion.
"""

import json
import plistlib
import re
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "shortcuts/Import_Day_One_to_Journal.xml"


class Stopped(Exception):
    pass


class Evaluator:
    def __init__(self, variables=None, files=None, picks=(), menu="Use export folder"):
        self.variables = dict(variables or {})
        self.outputs = {}
        self.files = dict(files or {})
        self.picks = iter(picks)
        self.menu = menu
        self.alerts = []

    def value(self, value):
        if not isinstance(value, dict):
            return value
        if "WFSerializationType" in value:
            return self.value(value["Value"])
        if value.get("Type") == "Variable":
            if "Variable" in value:
                return self.value(value["Variable"])
            return self.variables.get(value["VariableName"])
        if value.get("Type") == "ActionOutput":
            return self.outputs[value["OutputUUID"]]
        if "string" in value:
            text = value["string"]
            for position, token in sorted(value.get("attachmentsByRange", {}).items(),
                                          key=lambda item: int(re.search(r"\d+", item[0])[0]), reverse=True):
                start = int(re.search(r"\d+", position)[0])
                resolved = self.value(token)
                text = text[:start] + ("" if resolved is None else str(resolved)) + text[start + 1:]
            return text
        return value

    def condition(self, p):
        if "WFConditions" in p:
            table = p["WFConditions"]["Value"]
            values = [self.condition(t) for t in table["WFActionParameterFilterTemplates"]]
            return all(values) if table["WFActionParameterFilterPrefix"] == 1 else any(values)
        value = self.value(p["WFInput"])
        code = p["WFCondition"]
        if code in (100, 101):
            present = value is not None and value != "" and value != [] and value != {}
            return present if code == 100 else not present
        number = float(self.value(p.get("WFNumberValue", 0)))
        return {0: lambda: float(value) < number, 2: lambda: float(value) > number}[code]()

    def run(self, actions):
        stack = []
        active = True
        for action in actions:
            ident = action["WFWorkflowActionIdentifier"].removeprefix("is.workflow.actions.")
            p = action["WFWorkflowActionParameters"]
            mode = p.get("WFControlFlowMode")
            if ident in ("conditional", "choosefrommenu"):
                if mode == 0:
                    decision = self.condition(p) if active and ident == "conditional" else False
                    stack.append((active, decision))
                    active = active and decision
                elif mode == 1:
                    parent, decision = stack[-1]
                    active = parent and (not decision if ident == "conditional" else p["WFMenuItemTitle"] == self.menu)
                else:
                    active = stack.pop()[0]
                continue
            if not active:
                continue
            result = None
            incoming = self.value(p.get("WFInput"))
            if ident == "comment":
                continue
            elif ident == "file.select":
                result = next(self.picks)
            elif ident == "file.getfoldercontents":
                folder = self.value(p["WFFolder"])
                result = [path for path in self.files if str(Path(path).parent) == folder]
            elif ident == "documentpicker.open":
                path = str(Path(self.value(p["WFFile"])) / p["WFGetFilePath"])
                if path not in self.files and p.get("WFFileErrorIfNotFound", True):
                    raise FileNotFoundError(path)
                result = path if path in self.files else None
            elif ident == "documentpicker.save":
                path = str(Path(self.value(p["WFFolder"])) / p["WFFileDestinationPath"])
                self.files[path] = json.dumps(incoming)
                result = path
            elif ident == "filter.files":
                result = []
                for path in self.value(p["WFContentItemInputParameter"]):
                    matches = []
                    for f in p["WFContentItemFilter"]["Value"]["WFActionParameterFilterTemplates"]:
                        actual = Path(path).suffix[1:] if f["Property"] == "File Extension" else Path(path).name
                        wanted = self.value(f["Values"]["String"])
                        matches.append({4: lambda: actual == wanted, 999: lambda: wanted not in actual}[f["Operator"]]())
                    if all(matches):
                        result.append(path)
                if p.get("WFContentItemLimitEnabled"):
                    result = result[:int(p["WFContentItemLimitNumber"])]
            elif ident == "choosefromlist":
                result = next(self.picks)
                if result not in incoming:
                    raise AssertionError("Selection outside filtered candidates")
            elif ident == "setvariable":
                self.variables[p["WFVariableName"]] = incoming
                result = incoming
            elif ident == "detect.text":
                if isinstance(incoming, list) and len(incoming) == 1:
                    incoming = incoming[0]
                result = self.files.get(incoming, incoming) if isinstance(incoming, str) else incoming
            elif ident == "detect.dictionary":
                result = json.loads(incoming)
            elif ident == "dictionary":
                result = {}
            elif ident == "getvalueforkey":
                result = (incoming or {}).get(self.value(p["WFDictionaryKey"]))
            elif ident == "count":
                result = len((incoming or "").split()) if p.get("WFCountType") == "Words" else len(incoming or [])
            elif ident == "math":
                operand = float(self.value(p["WFMathOperand"]))
                result = float(incoming) - operand if p.get("WFMathOperation") == "-" else float(incoming) + operand
            elif ident == "getitemfromlist":
                if p.get("WFItemSpecifier") == "Items in Range":
                    start = int(self.value(p.get("WFItemRangeStart", "1"))) - 1
                    end = self.value(p.get("WFItemRangeEnd"))
                    result = incoming[start:int(end) if end is not None else None]
                else:
                    result = incoming[0] if incoming else None
            elif ident == "text.split":
                result = (self.value(p["text"]) or "").splitlines()
            elif ident == "text.combine":
                result = "\n".join(self.value(p["text"]))
            elif ident == "text.trimwhitespace":
                result = (incoming or "").strip()
            elif ident == "text.replace":
                result = re.sub(p["WFReplaceTextFind"], p.get("WFReplaceTextReplace", ""), incoming or "")
            elif ident in ("getrichtextfrommarkdown",):
                result = incoming
            elif ident == "askllm":
                result = "Synthetic title"
            elif ident == "gettext":
                result = self.value(p["WFTextActionText"])
            elif ident == "nothing":
                pass
            elif ident == "alert":
                self.alerts.append(p)
            elif ident == "exit":
                raise Stopped()
            else:
                raise AssertionError(f"Unsupported offline action: {ident}")
            if "UUID" in p:
                self.outputs[p["UUID"]] = result
        assert not stack, "Fragment has unbalanced control flow"


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.actions = plistlib.loads(SOURCE.read_bytes())["WFWorkflowActions"]

    def index(self, *, uuid=None, variable=None, key=None):
        for i, a in enumerate(self.actions):
            p = a["WFWorkflowActionParameters"]
            if ((uuid is not None and p.get("UUID") == uuid) or
                (variable is not None and p.get("WFVariableName") == variable) or
                (key is not None and p.get("WFDictionaryKey") == key)):
                return i
        raise AssertionError("Action missing")

    def preflight(self, entries, ledger=None, *, separate=False, extra_files=None):
        files = {"/export/Journal.json": json.dumps({"entries": entries})}
        folder = "/history" if separate else "/export"
        if ledger is not None:
            files[folder + "/already_imported_uuids.json"] = json.dumps(ledger)
        files.update(extra_files or {})
        picks = ["/export"] + ([folder] if separate else []) + ["/export/Journal.json"]
        runner = Evaluator(files=files, picks=picks, menu="Choose existing ledger folder" if separate else "Use export folder")
        end = next(i for i, a in enumerate(self.actions) if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.repeat.each")
        runner.run(self.actions[:end])
        return runner

    def test_nonprefix_and_prefiltered_exports_keep_all_candidates(self):
        for uuids, ledger in [("ABC", {"B": "true"}), ("BCD", {"A": "true"}), ("ABC", {})]:
            with self.subTest(uuids=uuids, ledger=ledger):
                entries = [{"uuid": uuid} for uuid in uuids]
                runner = self.preflight(entries, ledger)
                self.assertEqual(runner.variables["Entries"], entries)

    def test_ledger_is_not_an_export_candidate(self):
        runner = self.preflight([{"uuid": "B"}], {"A": "true"})
        filtered = self.actions[self.index(uuid="02790C4D-34A6-4EC9-92C5-6D2A57E46399")]["WFWorkflowActionParameters"]["UUID"]
        self.assertEqual(runner.outputs[filtered], ["/export/Journal.json"])

    def test_multiple_exports_require_selection(self):
        runner = self.preflight([{"uuid": "B"}], {}, extra_files={"/export/Other.json": '{"entries":[{"uuid":"wrong"}]}'})
        self.assertEqual(runner.variables["Entries"], [{"uuid": "B"}])
        filtered = runner.outputs["02790C4D-34A6-4EC9-92C5-6D2A57E46399"]
        self.assertEqual(len(filtered), 2)

    def test_empty_export_stops_before_repeat(self):
        with self.assertRaises(Stopped):
            self.preflight([], {})

    def test_no_export_json_stops_before_selection(self):
        runner = Evaluator(files={"/export/already_imported_uuids.json": '{}'}, picks=["/export"])
        end = next(i for i, a in enumerate(self.actions) if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.repeat.each")
        with self.assertRaises(Stopped):
            runner.run(self.actions[:end])
        self.assertTrue(runner.alerts)

    def eligibility(self, entry, ledger):
        start = self.index(uuid="21BD92D5-4211-4849-B602-6515ECEE0F08")
        end = self.index(uuid="872C5EE5-C3A5-4EE4-A12E-24C3EF02C07D")
        # Replace the import body with a sentinel; retain the actual skip branch
        # and its End If. No Journal or AI action is evaluated in this fragment.
        marker = {"WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
                  "WFWorkflowActionParameters": {"WFVariableName": "Eligible", "WFInput": True}}
        close = self.actions[self.index(uuid="C6F7D616-FE7F-47F3-837F-4B461AEB29F9")]
        runner = Evaluator({"Repeat Item": entry, "AlreadyImportedUUIDsDictionary": ledger})
        runner.run(self.actions[start:end] + [marker, close])
        return runner.variables.get("Eligible", False)

    def test_uuid_lookup_skips_only_recorded_entries(self):
        ledger = {"B": "true"}
        self.assertEqual([uuid for uuid in "ABC" if self.eligibility({"uuid": uuid}, ledger)], ["A", "C"])
        ledger["A"] = "true"
        self.assertFalse(self.eligibility({"uuid": "A"}, ledger))

    def test_missing_uuid_stops_before_import(self):
        for entry in [{}, {"uuid": ""}]:
            with self.subTest(entry=entry), self.assertRaises(Stopped):
                self.eligibility(entry, {})

    def test_new_import_initializes_ledger(self):
        runner = self.preflight([{"uuid": "A"}])
        self.assertEqual(runner.variables["AlreadyImportedUUIDsDictionary"], {})

    def test_separate_ledger_is_required_and_saved_in_same_folder(self):
        with self.assertRaises(FileNotFoundError):
            self.preflight([{"uuid": "B"}], separate=True)
        runner = self.preflight([{"uuid": "B"}], {"A": "true"}, separate=True)
        self.assertEqual(runner.variables["AlreadyImportedUUIDsDictionary"], {"A": "true"})
        runner.variables["AlreadyImportedUUIDsDictionary"]["B"] = "true"
        runner.run([self.actions[self.index(uuid="367F2BF4-FD51-4F86-BFBE-CCD82A79ECBB")]])
        self.assertEqual(json.loads(runner.files["/history/already_imported_uuids.json"]), {"A": "true", "B": "true"})
        self.assertNotIn("/export/already_imported_uuids.json", runner.files)

    def test_generated_title_preserves_current_body_on_first_and_later_entries(self):
        start = self.index(uuid="6BC69E40-96A9-4159-B05F-44C1B4A28BBA")
        end = self.index(uuid="0B9F7F72-9FE8-4E47-8DC1-14046C168138") + 1
        runner = Evaluator()
        for body in ["A long first line with more than twelve words needs a generated title for this entry.",
                     "Old title\nOld body", "Another long opening line with more than twelve words must keep its own current body."]:
            runner.variables["Repeat Item"] = {"text": body}
            runner.run(self.actions[start:end])
            self.assertEqual(runner.variables["EntryTextWithoutTitle"], "Old body" if body.startswith("Old title") else body)

    def test_location_values_do_not_leak_between_entries(self):
        start = self.index(uuid="8144AA36-F371-4EB6-97A8-A39C5163A2A4")
        end = self.index(uuid="0E1B0FF5-8AD7-4794-910D-ED9BE2ECAFCE") + 1
        runner = Evaluator()
        runner.variables["Repeat Item"] = {"location": {"placeName": "Synthetic Park", "localityName": "Test Town"}}
        runner.run(self.actions[start:end])
        self.assertIn("Synthetic Park", runner.variables["DayOneLocation"])
        runner.variables["Repeat Item"] = {}
        runner.run(self.actions[start:end])
        for name in ["DayOneLocation", "PlaceName", "LocalityName", "Country", "AdministrativeArea", "Latitude", "Longitude", "UserLabel"]:
            self.assertFalse(runner.variables.get(name), name)

    def test_unsupported_actions_cannot_run(self):
        journal = next(a for a in self.actions if a["WFWorkflowActionIdentifier"].startswith("com.apple.journal."))
        with self.assertRaises(AssertionError):
            Evaluator().run([journal])


if __name__ == "__main__":
    unittest.main()
