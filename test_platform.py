"""Meaningful verification; synthetic fixtures here are tests, never clinical outputs."""
import copy, io, json, sys, unittest
import numpy as np
import pandas as pd
from engine import ROOT, resources, infer, import_npz
from analysis import event_weights, evaluate, selected

class AnalysisTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({'patient_key':['a','b','c','d','e','f','g','h','i','j'], 'duration_days':[30,40,500,500,500,500,500,500,500,500], 'event_type':[1,2,0,0,0,0,0,0,0,0], 'a':[.9,.8,.7,.6,.5,.4,.3,.2,.1,0], 'b':[0,.9,.8,.7,.6,.5,.4,.3,.2,.1]})
    def test_fixed_capacity_and_competing_death(self):
        f=self.fixture()
        w,g,c=event_weights(f,360)
        self.assertEqual(w.sum(),1)
        self.assertEqual(g,1)
        result=evaluate(f,['a','b'],12,fractions=(.1,.2),bootstrap=200)
        delta=result['comparison'].iloc[0]
        self.assertEqual(delta.extra_captured_per1000,100)
        self.assertEqual(delta.change_non_event_reviews_per1000,-100)
        self.assertEqual(result['quality']['competing_deaths'],1)
        self.assertEqual(result['table'].selected_n.min(),1)
    def test_censor_weight_not_death_weight(self):
        f=pd.DataFrame({'duration_days':[10,20,30,360],'event_type':[0,2,1,0]})
        w,g,c=event_weights(f,360)
        self.assertAlmostEqual(w[2],4/3)
        self.assertAlmostEqual(g,.75)
        self.assertEqual(c,1)
    def test_no_events_and_no_support(self):
        f=self.fixture()
        f['event_type']=0
        with self.assertRaisesRegex(ValueError,'没有已观察'):
            evaluate(f,['a','b'],12)
        f=self.fixture()
        f.loc[1:,'duration_days']=10
        f.loc[1:,'event_type']=0
        with self.assertRaisesRegex(ValueError,'随访支持不足'):
            evaluate(f,['a','b'],60)
    def test_ties_ignore_outcome_and_duplicates_rejected(self):
        f=self.fixture().assign(a=.5)
        mask=selected(f,'a',.1)
        self.assertEqual(f.loc[mask,'patient_key'].iloc[0],'a')
        f.loc[1,'patient_key']='a'
        with self.assertRaisesRegex(ValueError,'重复'):
            evaluate(f,['a'],12)
    def test_npz_axes_and_seed(self):
        payload={'patient_key_fu0':np.array(['a','b']),'duration_days_fu0':np.array([[[10,50]],[[20,70]]]),'event_type_fu0':np.array([[[1,0]],[[2,0]]]),'risk_02_fu0':np.ones((2,1,2,5))*.1,'risk_03_fu0':np.ones((2,1,2,5))*.2,'seed':np.array([42,123]),'analysis':np.array(['primary']),'source_sha256':np.array('test')}
        content=io.BytesIO()
        np.savez_compressed(content,**payload)
        frame,_,m=import_npz(content.getvalue(),seed_index=1)
        self.assertEqual(m['seed'],123)
        self.assertEqual(frame.duration_days.tolist(),[20,70])
        self.assertEqual(len(frame),2)

class ModelTests(unittest.TestCase):
    def record(self):
        return {'test-patient':{'birthdate':'1970-01-01','gender':'男','end_of_data':'2021-01-01','death_date':None,'events':[{'admdate':'2020-01-01','codes':'E11'},{'admdate':'2020-01-15','codes':'I10'},{'admdate':'2020-02-01','codes':'I10'}]}}
    def test_future_information_does_not_change_prediction(self):
        a=self.record()
        b=copy.deepcopy(a)
        b['test-patient']['events'].append({'admdate':'2020-03-01','codes':'I21'})
        b['test-patient']['death_date']='2020-04-01'
        b['test-patient']['end_of_data']='2020-05-01'
        first,_,_=infer(a,'current','2020-02-15')
        second,_,_=infer(b,'current','2020-02-15')
        cols=[c for c in first if c.startswith('risk_')]
        np.testing.assert_allclose(first[cols],second[cols],atol=1e-7)
        self.assertEqual(first.assessment_date.iloc[0],'2020-02-15')
        self.assertTrue((np.diff(first[[f'risk_02_{h}' for h in [3,6,12,36,60]]].values)>=0).all())
    def test_adapter_matches_original_on_identical_landmark(self):
        import torch
        from datetime import date
        _,vendor,_,cfg,models=resources()
        p=vendor.Patient('test',date(1970,1,1),1.,date(2021,1,1),vendor.MISSING,vendor.MISSING,vendor.process_events(self.record()['test-patient']['events'],cfg),{})
        expected=vendor.predict(models['02'],[(p,len(p.events)-1)],cfg,torch.device('cpu'),1)
        frame,_,_=infer(self.record(),'current','2020-02-01')
        np.testing.assert_allclose(expected,frame[[f'risk_02_{h}' for h in [3,6,12,36,60]]],atol=1e-6)
    def test_prevalent_cvd_and_missing_gender_rejected(self):
        record=self.record()
        record['test-patient']['events'].append({'admdate':'2020-01-15','codes':'I21'})
        with self.assertRaisesRegex(ValueError,'已有目标 CVD'):
            infer(record,'current','2020-02-01')
        record=self.record()
        record['test-patient']['gender']=None
        with self.assertRaisesRegex(ValueError,'性别'):
            infer(record)

class UItests(unittest.TestCase):
    def test_hospital_linked_inputs_and_interface(self):
        from engine import sample_path
        sample=json.loads(sample_path().read_text(encoding='utf-8'))
        hospital=json.loads((ROOT/'data/hospital_linked_200.json').read_text(encoding='utf-8'))
        self.assertEqual(set(sample),set(hospital))
        _,vendor,_,_,_=resources()
        for key in sample:
            self.assertEqual(sample[key]['birthdate'],hospital[key]['birthdate'])
            self.assertEqual(vendor.gender_value(sample[key]['gender']),vendor.gender_value(hospital[key]['gender']))
        report=json.loads((ROOT/'reports/hospital_linkage_report.json').read_text(encoding='utf-8'))
        self.assertGreater(report['lab_events'],0)
        self.assertGreater(report['med_events'],0)
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        at.sidebar.radio[0].set_value('患者风险与复查排序').run()
        next(s for s in at.selectbox if s.label=='数据来源').set_value('省立医院关联样本（真实院内表）').run()
        self.assertFalse(at.exception)
        self.assertEqual(next(m for m in at.metric if m.label=='可评估患者').value,'145')
    def test_app_navigation_and_empty_event_handling(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        self.assertFalse(at.exception)
        at.sidebar.radio[0].set_value('患者风险与复查排序').run()
        self.assertGreater(len(at.metric),0)
        at.sidebar.radio[0].set_value('资源约束验证').run()
        self.assertFalse(at.exception)
        calculate=next(b for b in at.button if b.label.startswith('计算 5%'))
        calculate.click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any('没有已观察' in e.value for e in at.error))
        at.sidebar.radio[0].set_value('数据接入与模型说明').run()
        self.assertFalse(at.exception)
        self.assertGreater(len(at.dataframe),0)
        at.sidebar.radio[0].set_value('患者风险与复查排序').run()
        source=next(x for x in at.selectbox if x.label=='数据来源')
        source.set_value('上传患者 JSON').run()
        self.assertFalse(at.exception)
        self.assertTrue(next(b for b in at.button if b.label=='运行真实模型').disabled)
        self.assertEqual(len(at.metric),0)
    def test_english_product_and_clinical_view(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        at.sidebar.selectbox[0].set_value('English').run()
        self.assertFalse(at.exception)
        self.assertTrue(any('clinician-facing' in h.value for h in at.subheader))
        at.sidebar.radio[0].set_value('患者风险与复查排序').run()
        self.assertFalse(at.exception)
        self.assertTrue(any(m.label=='Patients with predictions' for m in at.metric))
        self.assertTrue(any(s.label=='Data source' for s in at.selectbox))
        at.sidebar.radio[0].set_value('资源约束验证').run()
        self.assertFalse(at.exception)
        self.assertTrue(any('contains no recorded target' in i.value for i in at.info))
        at.sidebar.radio[0].set_value('数据接入与模型说明').run()
        self.assertFalse(at.exception)
        self.assertTrue(any(s.value=='Data and model integration status' for s in at.subheader))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (ROOT/'reports'/'verification.json').write_text(json.dumps({'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful()},indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
