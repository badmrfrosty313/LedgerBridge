import csv
import io
import tempfile
import threading
import unittest
from pathlib import Path

from ledgerbridge.core import Store, WorkflowError
from ledgerbridge.bridge import DemoBridge
from ledgerbridge.mock_erp import MockERP


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/"ledger.sqlite3")
        self.document=self.store.import_csv("vendor,date,total,account_code,department,notes\nSYNTHETIC MAPPING VENDOR,2026-10-12,100.00,5100,Operations,Test posting","synthetic.csv","Importer")[0]["id"]

    def tearDown(self): self.temp.cleanup()

    def approve(self):
        row=self.store.detail(self.document)
        self.store.transition(self.document,"approve",row["revision"],"Reviewer",independent=True)

    def test_dry_run_is_non_persistent_and_profile_mapping_is_versioned(self):
        self.approve()
        preview=self.store.mapping_dry_run()
        self.assertEqual(preview["difference_cents"],0)
        self.assertEqual(preview["source_total_cents"],10000)
        self.assertEqual(preview["mapped_total_cents"],10000)
        self.assertEqual(preview["rows"][0]["account_code"],"5100")
        self.assertEqual(self.store.exports(),[])
        profile=self.store.mapping_profile()
        changed=profile["profile"]|{"account_map":profile["profile"]["account_map"]|{"5100":"510000"}}
        self.store.save_mapping_profile(changed,profile["revision"],"Admin")
        with self.assertRaises(WorkflowError): self.store.confirm_mapping_export(preview["preview_id"],preview["profile_revision"],"Admin")
        refreshed=self.store.mapping_dry_run()
        self.assertEqual(refreshed["rows"][0]["account_code"],"510000")
        self.assertEqual(refreshed["profile_revision"],profile["revision"]+1)
        with self.assertRaises(WorkflowError): self.store.confirm_mapping_export(refreshed["preview_id"],refreshed["profile_revision"],"Admin")
        exported=self.store.confirm_mapping_export(refreshed["preview_id"],refreshed["profile_revision"],"Approver")
        self.assertEqual(exported["difference_cents"],0)

    def test_unmapped_account_blocks_confirm_until_profile_is_fixed(self):
        self.approve()
        profile=self.store.mapping_profile()
        updated=profile["profile"]|{"account_map":{}}
        self.store.save_mapping_profile(updated,profile["revision"],"Admin")
        dry=self.store.mapping_dry_run()
        self.assertEqual(dry["rows"],[])
        self.assertEqual(dry["rejected"][0]["source_id"],self.document)
        with self.assertRaises(WorkflowError): self.store.confirm_mapping_export(dry["preview_id"],dry["profile_revision"],"Admin")
        self.assertEqual(self.store.exports(),[])

    def test_explicit_mapped_export_is_immutable_and_reconcilable(self):
        row=self.store.detail(self.document)
        self.store.save_allocations(self.document,[{"destination":"Fund A","percent":"60"},{"destination":"Fund B","percent":"40"}],row["revision"],"Allocator")
        self.approve()
        profile=self.store.mapping_profile()
        self.store.save_mapping_profile(profile["profile"]|{"expand_allocations":True},profile["revision"],"Admin")
        preview=self.store.mapping_dry_run()
        self.assertEqual([item["destination"] for item in preview["rows"]],["Fund A","Fund B"])
        self.assertEqual(preview["source_total_cents"],preview["mapped_total_cents"])
        self.assertEqual(preview["difference_cents"],0)
        self.assertEqual(self.store.exports(),[])
        with self.assertRaises(WorkflowError): self.store.confirm_mapping_export(preview["preview_id"],preview["profile_revision"],"Admin")
        exported=self.store.confirm_mapping_export(preview["preview_id"],preview["profile_revision"],"Approver")
        content=self.store.export_content(exported["id"])
        rows=list(csv.DictReader(io.StringIO(content)))
        self.assertEqual([item["total"] for item in rows],["60.00","40.00"])
        self.assertTrue(all(item["source_id"]==self.document for item in rows))
        self.assertEqual(self.store.detail(self.document)["status"],"exported")
        self.assertEqual(self.store.mapping_dry_run()["rows"],[])
        with self.assertRaises(WorkflowError): self.store.edit(self.document,{"total_cents":12000},self.store.detail(self.document)["revision"],"Reviewer")
        with self.store.connect() as db:
            meta=db.execute("SELECT * FROM mapping_export_meta WHERE export_id=?",(exported["id"],)).fetchone()
            self.assertEqual(meta["source_total_cents"],10000)
            self.assertEqual(meta["mapped_total_cents"],10000)

    def test_mapped_snapshot_is_accepted_by_simulated_erp_once(self):
        self.approve(); dry=self.store.mapping_dry_run()
        exported=self.store.confirm_mapping_export(dry["preview_id"],dry["profile_revision"],"Admin")
        target=MockERP(Path(self.temp.name)/"target.sqlite3")
        bridge=DemoBridge(self.store); bridge.request=lambda path,body=None: target.accept(body) if body is not None else {"status":"ok"}
        receipt=bridge.send(exported["id"],"Admin")
        replay=bridge.send(exported["id"],"Admin")
        self.assertFalse(receipt["replayed"]); self.assertTrue(replay["replayed"])
        self.assertEqual(receipt["record_count"],1)
        self.assertEqual(target.ledger()[0]["total_cents"],10000)

    def test_concurrent_export_confirmation_is_exactly_once(self):
        self.approve(); preview=self.store.mapping_dry_run(); barrier=threading.Barrier(2); outcomes=[]
        def confirm(actor):
            barrier.wait()
            try:
                result=self.store.confirm_mapping_export(preview["preview_id"],preview["profile_revision"],actor)
                outcomes.append(("exported",result["id"]))
            except WorkflowError:
                outcomes.append(("stale",None))
        workers=[threading.Thread(target=confirm,args=(name,)) for name in ("Reviewer A","Reviewer B")]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        self.assertCountEqual([result[0] for result in outcomes],["exported","stale"])
        self.assertEqual(len(self.store.exports()),1)
        self.assertEqual(self.store.detail(self.document)["status"],"exported")

    def test_corrupted_persisted_mapping_profile_blocks_preview_and_confirmation_safely(self):
        self.approve(); profile=self.store.mapping_profile()
        with self.store.connect(write=True) as db:
            db.execute("UPDATE mapping_profiles SET profile=? WHERE id=1",('{"profile_version":1,"account_map":[],"expand_allocations":false}',))
        with self.assertRaisesRegex(WorkflowError,"Stored mapping profile is invalid"):
            self.store.mapping_dry_run()
        with self.assertRaisesRegex(WorkflowError,"Stored mapping profile is invalid"):
            self.store.confirm_mapping_export("0"*64,profile["revision"],"Reviewer")

    def test_round_trip_reconciliation_reports_export_and_received_cents(self):
        self.approve()
        preview=self.store.mapping_dry_run()
        exported=self.store.confirm_mapping_export(preview["preview_id"],preview["profile_revision"],"Exporter")
        target=MockERP(Path(self.temp.name)/"reconcile-target.sqlite3")
        bridge=DemoBridge(self.store)
        bridge.request=lambda path,body=None: target.accept(body) if body is not None else target.batch_summary(path.rsplit("/",1)[-1])
        pending=bridge.reconciliation()[0]
        self.assertEqual(pending["delivery_state"],"not_sent")
        bridge.send(exported["id"],"Delivery Admin")
        row=bridge.reconciliation()[0]
        self.assertEqual(row["delivery_state"],"reconciled")
        self.assertEqual((row["source_total_cents"],row["mapped_total_cents"],row["export_total_cents"],row["received_total_cents"]),(10000,10000,10000,10000))
        self.assertEqual(row["source_mapping_difference_cents"],0)
        self.assertEqual(row["mapping_export_difference_cents"],0)
        self.assertEqual(row["export_received_difference_cents"],0)


if __name__=="__main__": unittest.main()
