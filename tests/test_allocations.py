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
