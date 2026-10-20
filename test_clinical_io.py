import unittest
from clinical_io import detect,event_table,synthetic_patients,report

class ClinicalIOTests(unittest.TestCase):
    def test_gb18030_and_utf8_round_trip(self):
        records=synthetic_patients(3)
        for encoding in ['gb18030','utf-8-sig']:
            result,audit=detect(event_table(records).to_csv(index=False).encode(encoding),'export.rds')
            self.assertEqual(records,result)
            self.assertTrue(audit['requires_mapping_confirmation'])
    def test_ambiguous_mapping_and_missing_demographics_rejected(self):
        df=event_table(synthetic_patients(1));df['患者编号']=df.patient_id
        with self.assertRaisesRegex(ValueError,'Ambiguous'):detect(df.to_csv(index=False).encode(),'a.csv')
        with self.assertRaisesRegex(ValueError,'Missing'):detect(df.drop(columns=['患者编号','birthdate']).to_csv(index=False).encode(),'a.csv')
    def test_unreviewed_and_past_date_reports_rejected(self):
        row={'patient_key':'SYNTHETIC','risk_02_12':.2}
        with self.assertRaises(ValueError):report(row,'02',12,'Reviewer','2025-02-01','2025-01-01')
        with self.assertRaises(ValueError):report(row,'02',12,'Reviewer','2024-02-01','2025-01-01',approved=True)
    def test_bilingual_report_is_escaped_and_explicitly_synthetic(self):
        row={'patient_key':'<SYNTHETIC>','risk_02_12':.2}
        zh=report(row,'02',12,'<Reviewer>','2025-02-01','2025-01-01','zh',True)
        en=report(row,'02',12,'<Reviewer>','2025-02-01','2025-01-01','en',True)
        self.assertIn('合成病例',zh);self.assertIn('Synthetic',en)
        self.assertIn('&lt;Reviewer&gt;',en);self.assertNotIn('<Reviewer>',en)
        self.assertIn('20.0%',zh)

if __name__=='__main__':unittest.main()
