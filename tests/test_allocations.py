import tempfile, unittest
from pathlib import Path
from ledgerbridge.core import Store, WorkflowError

class AllocationTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/"db.sqlite3"); self.doc=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,0.01,5100", "synthetic.csv", "Reviewer")[0]["id"]
 def tearDown(self): self.tmp.cleanup()
 def test_one_cent_and_negative_allocate_exactly(self):
  preview=self.store.allocation_preview(self.doc,[{"destination":"Fund A","percent":"50.0000"},{"destination":"Fund B","percent":"50.0000"}]); self.assertEqual(sum(x["cents"] for x in preview["items"]),1); self.assertEqual(preview["items"][0]["cents"],1)
  doc=self.store.detail(self.doc); saved=self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],doc["revision"],"Reviewer"); self.assertEqual(saved["status"],"draft")
 def test_rejects_non_balancing_percentages(self):
  with self.assertRaises(WorkflowError): self.store.allocation_preview(self.doc,[{"destination":"Fund A","percent":"99.9999"}])
 def test_allocation_contributor_cannot_independently_approve_or_bypass_rejection(self):
  doc=self.store.detail(self.doc); self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],doc["revision"],"Allocator")
  current=self.store.detail(self.doc)
  with self.assertRaises(WorkflowError): self.store.transition(self.doc,"approve",current["revision"],"Allocator",independent=True)
  rejected=self.store.transition(self.doc,"reject",current["revision"],"Reviewer","Synthetic rejection")
  with self.assertRaises(WorkflowError): self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],rejected["revision"],"Allocator")
 def test_saved_allocations_are_read_back(self):
  doc=self.store.detail(self.doc); saved=self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],doc["revision"],"Allocator")
  self.assertEqual(saved["allocations"][0]["cents"], 1)
 def test_total_edit_removes_allocations_and_requires_fresh_approval(self):
  doc=self.store.detail(self.doc); self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],doc["revision"],"Allocator")
  doc=self.store.detail(self.doc); changed=self.store.edit(self.doc,{"total_cents":2},doc["revision"],"Reviewer")
  self.assertEqual(changed["allocations"],[])
  self.assertTrue(any(event["action"]=="allocations_invalidated" for event in changed["events"]))
  with self.assertRaises(WorkflowError): self.store.transition(self.doc,"approve",changed["revision"],"Approver")
 def test_corrupt_persisted_allocation_blocks_approval_and_export(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  with self.store.connect(write=True) as db: db.execute("UPDATE allocations SET cents=9999 WHERE document_id=? AND destination='Fund A'",(document,))
  doc=self.store.detail(document); self.assertIn("allocation_stale",[issue["code"] for issue in doc["issues"]])
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",doc["revision"],"Approver",independent=True)
 def test_hundred_dollar_allocation_approves_and_exports_legacy_total(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  doc=self.store.detail(document); self.store.transition(document,"approve",doc["revision"],"Approver",independent=True)
  exported=self.store.export("Admin"); self.assertIn("100.00",self.store.export_content(exported["id"]))
 def test_templates_are_persisted_and_audited(self):
  templates=self.store.save_allocation_template("Synthetic split",[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],"Admin")
  self.assertEqual(templates[0]["name"],"Synthetic split")
  self.assertTrue(any(event["action"]=="allocation_template_saved" for event in self.store.events()))
