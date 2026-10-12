import tempfile, threading, unittest
from pathlib import Path
from ledgerbridge.core import Store, WorkflowError

class AllocationTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/"db.sqlite3"); self.doc=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,0.01,5100", "synthetic.csv", "Reviewer")[0]["id"]
 def tearDown(self): self.tmp.cleanup()
 def test_one_cent_and_negative_allocate_exactly(self):
  preview=self.store.allocation_preview(self.doc,[{"destination":"Fund A","percent":"50.0000"},{"destination":"Fund B","percent":"50.0000"}]); self.assertEqual(sum(x["cents"] for x in preview["items"]),1); self.assertEqual(preview["items"][0]["cents"],1)
  doc=self.store.detail(self.doc); saved=self.store.save_allocations(self.doc,[{"destination":"Fund A","percent":"100"}],doc["revision"],"Reviewer"); self.assertEqual(saved["status"],"draft")
 def test_multiway_rounding_is_stable_and_signed(self):
  rows=[{"destination":"Fund C","percent":"33.3333"},{"destination":"Fund A","percent":"33.3334"},{"destination":"Fund B","percent":"33.3333"}]
  with self.store.connect(write=True) as db: db.execute("UPDATE documents SET fields=json_set(fields,'$.total_cents',2) WHERE id=?",(self.doc,))
  positive=self.store.allocation_preview(self.doc,rows)
  self.assertEqual([(x["destination"],x["cents"]) for x in positive["items"]],[ ("Fund C",0),("Fund A",1),("Fund B",1)])
  self.assertEqual(positive["allocated_cents"],2)
  with self.store.connect(write=True) as db: db.execute("UPDATE documents SET fields=json_set(fields,'$.total_cents',-2) WHERE id=?",(self.doc,))
  negative=self.store.allocation_preview(self.doc,rows)
  self.assertEqual([(x["destination"],x["cents"]) for x in negative["items"]],[ ("Fund C",0),("Fund A",-1),("Fund B",-1)])
  self.assertEqual(negative["allocated_cents"],-2)
 def test_zero_total_preview_reconciles_without_float_math(self):
  with self.store.connect(write=True) as db: db.execute("UPDATE documents SET fields=json_set(fields,'$.total_cents',0) WHERE id=?",(self.doc,))
  preview=self.store.allocation_preview(self.doc,[{"destination":"Fund A","percent":"25.125"},{"destination":"Fund B","percent":"74.875"}])
  self.assertEqual([item["cents"] for item in preview["items"]],[0,0])
  self.assertEqual(preview["difference_cents"],0)
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
 def test_total_change_requires_reallocation_then_allows_independent_approval_and_export(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC TOTAL REVISION,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  current=self.store.detail(document)
  saved=self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],current["revision"],"Allocator")
  changed=self.store.edit(document,{"total_cents":12000},saved["revision"],"Editor")
  self.assertIn("allocation_review_required",[issue["code"] for issue in changed["issues"]])
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",changed["revision"],"Approver",independent=True)
  resaved=self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],changed["revision"],"Allocator")
  self.assertNotIn("allocation_review_required",[issue["code"] for issue in resaved["issues"]])
  approved=self.store.transition(document,"approve",resaved["revision"],"Approver",independent=True)
  self.assertEqual(approved["status"],"approved")
  result=self.store.export("Admin")
  self.assertIn("120.00",self.store.export_content(result["id"]))
 def test_corrupt_persisted_allocation_blocks_approval_and_export(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  with self.store.connect(write=True) as db: db.execute("UPDATE allocations SET cents=9999 WHERE document_id=? AND destination='Fund A'",(document,))
  doc=self.store.detail(document); self.assertIn("allocation_stale",[issue["code"] for issue in doc["issues"]])
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",doc["revision"],"Approver",independent=True)
 def test_corrupt_percent_and_allocated_cents_block_approval_and_export(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC CORRUPTION,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  doc=self.store.detail(document); self.store.transition(document,"approve",doc["revision"],"Approver",independent=True)
  with self.store.connect(write=True) as db: db.execute("UPDATE allocations SET cents=9999 WHERE document_id=? AND destination='Fund A'",(document,))
  with self.assertRaises(WorkflowError): self.store.export("Admin")
  with self.store.connect(write=True) as db: db.execute("UPDATE allocations SET cents=6000,percent='nonsense' WHERE document_id=? AND destination='Fund A'",(document,))
  with self.assertRaises(WorkflowError): self.store.export("Admin")
 def test_approval_revalidates_corrupt_percentages_destinations_and_duplicate_rows(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC INTEGRITY MATRIX,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  with self.store.connect(write=True) as db: db.execute("UPDATE allocations SET percent='59' WHERE document_id=? AND destination='Fund A'",(document,))
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",self.store.detail(document)["revision"],"Approver",independent=True)
  with self.store.connect(write=True) as db:
   db.execute("UPDATE allocations SET percent='60' WHERE document_id=? AND destination='Fund A'",(document,))
   db.execute("UPDATE allocations SET destination='../unsafe' WHERE document_id=? AND destination='Fund B'",(document,))
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",self.store.detail(document)["revision"],"Approver",independent=True)
  with self.store.connect(write=True) as db:
   db.execute("DROP TABLE allocations")
   db.execute("CREATE TABLE allocations(document_id TEXT NOT NULL,destination TEXT NOT NULL,percent TEXT NOT NULL,cents INTEGER NOT NULL,revision INTEGER NOT NULL)")
   db.executemany("INSERT INTO allocations VALUES (?,?,?,?,?)",[(document,"Fund A","60",6000,2),(document,"Fund A","40",4000,2)])
  with self.assertRaises(WorkflowError): self.store.transition(document,"approve",self.store.detail(document)["revision"],"Approver",independent=True)
  with self.store.connect(write=True) as db: db.execute("UPDATE documents SET status='approved' WHERE id=?",(document,))
  with self.assertRaises(WorkflowError): self.store.export("Admin")
 def test_template_validation_revision_and_restart(self):
  valid=[{"destination":"Fund A","percent":"60.0000"},{"destination":"Fund B","percent":"40"}]
  for invalid in (None, [], valid+[valid[0]], [{"destination":"Fund A","percent":"99.9999"}], [{"destination":"Fund A","percent":"100.00001"}], [{"destination":"Fund A","percent":"NaN"}], [{"destination":"Fund A","percent":"100"},{"destination":"Fund A","percent":"0"}]):
   with self.assertRaises(WorkflowError): self.store.save_allocation_template("Bad template",invalid,"Admin")
  self.assertEqual(self.store.allocation_templates(),[])
  saved=self.store.save_allocation_template("Synthetic split",valid,"Admin")
  self.assertEqual(saved[0]["revision"],1)
  with self.assertRaises(WorkflowError): self.store.save_allocation_template("Synthetic split",valid,"Admin")
  updated=self.store.save_allocation_template("Synthetic split",valid,"Admin",revision=1)
  self.assertEqual(updated[0]["revision"],2)
  restarted=Store(self.store.path)
  self.assertEqual(restarted.allocation_templates()[0]["revision"],2)
  event=next(event for event in restarted.events() if event["action"]=="allocation_template_saved")
  self.assertEqual(event["actor"],"Admin")
 def test_old_versions_migrate_without_losing_documents(self):
  document=self.doc
  for version in (1,2,3,4,5):
   with self.subTest(version=version):
    with self.store.connect(write=True) as db:
     db.execute("PRAGMA user_version="+str(version))
     if version < 4: db.execute("DROP TABLE IF EXISTS allocation_templates")
     if version < 3: db.execute("DROP TABLE IF EXISTS allocation_state")
     if version < 2: db.execute("DROP TABLE IF EXISTS allocations")
     db.execute("DROP TABLE IF EXISTS mapping_profiles")
     db.execute("DROP TABLE IF EXISTS mapping_export_meta")
    migrated=Store(self.store.path)
    self.assertEqual(migrated.detail(document)["fields"]["total_cents"],1)
    with migrated.connect() as db: self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0],6)
 def test_concurrent_stale_allocation_confirmation_is_single_winner(self):
  revision=self.store.detail(self.doc)["revision"]
  barrier=threading.Barrier(2); outcomes=[]
  def save(destination):
   barrier.wait()
   try: self.store.save_allocations(self.doc,[{"destination":destination,"percent":"100"}],revision,destination); outcomes.append("saved")
   except WorkflowError: outcomes.append("stale")
  threads=[threading.Thread(target=save,args=(name,)) for name in ("Fund A","Fund B")]
  for thread in threads: thread.start()
  for thread in threads: thread.join()
  self.assertCountEqual(outcomes,["saved","stale"])
 def test_hundred_dollar_allocation_approves_and_exports_legacy_total(self):
  document=self.store.import_csv("vendor,date,total,account_code\nSYNTHETIC,2026-10-01,100.00,5100","synthetic.csv","Importer")[0]["id"]
  doc=self.store.detail(document); self.store.save_allocations(document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],doc["revision"],"Allocator")
  doc=self.store.detail(document); self.store.transition(document,"approve",doc["revision"],"Approver",independent=True)
  exported=self.store.export("Admin"); self.assertIn("100.00",self.store.export_content(exported["id"]))
 def test_templates_are_persisted_and_audited(self):
  templates=self.store.save_allocation_template("Synthetic split",[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],"Admin")
  self.assertEqual(templates[0]["name"],"Synthetic split")
  self.assertTrue(any(event["action"]=="allocation_template_saved" for event in self.store.events()))
 def test_corrupted_persisted_template_fails_with_controlled_error(self):
  self.store.save_allocation_template("Synthetic split",[{"destination":"Fund A","percent":"100"}],"Admin")
  with self.store.connect(write=True) as db: db.execute("UPDATE allocation_templates SET items='not-json' WHERE name='Synthetic split'")
  with self.assertRaisesRegex(WorkflowError,"Stored allocation template"):
   self.store.allocation_templates()
