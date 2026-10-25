"""Research drafts: real model output with no fabricated clinical approval."""
import html
from risk_profile import profile_html

def patient_draft(row,model='02',lang='zh',measurements=None):
    zh=lang=='zh';t=lambda a,b:a if zh else b;esc=lambda x:html.escape(str(x))
    title=t('患者风险报告 · 待医生审核','Patient risk report · pending clinician review')
    warning=t('历史资料研究草稿，尚未进行临床审核。不是当前诊断、治疗或复查医嘱。','Historical research draft; not clinically reviewed. This is not a current diagnosis, treatment or follow-up order.')
    fields=[(t('匿名编号','Pseudonymous ID'),row['patient_key']),(t('历史评估日期','Historical assessment date'),row['assessment_date']),
            (t('模型权重','Model weights'),'model_'+model),(t('审核医生','Reviewing clinician'),t('待确认','Pending')),
            (t('复查日期','Review date'),t('待医生确认；未自动生成','Pending clinician confirmation; not generated'))]
    body='<div class="notice">'+warning+'</div><table>'+''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v)+'</td></tr>' for k,v in fields)+'</table>'
    body+=profile_html(row,model,lang)
    if measurements:
        body+='<h2>'+t('可用的输入检验值','Usable supplied measurements')+'</h2><table>'+''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v)+'</td></tr>' for k,v in measurements)+'</table>'
    body+='<p>'+t('预测首次复合心血管事件，不表示已预防事件或某种药物的治疗效果。权重身份、源数据完整性和本地校准仍需核实。','Predictions concern first composite cardiovascular events, not prevented events or drug effects. Weight identity, source completeness and local calibration require verification.')+'</p>'
    return '<!doctype html><html lang="'+lang+'"><meta charset="utf-8"><title>'+title+'</title><style>body{max-width:1000px;margin:30px auto;padding:22px;font:16px/1.65 system-ui;color:#183247}h1{font-size:26px}.notice{background:#fff3d8;padding:15px;border-left:4px solid #c69843;margin:18px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px;border-bottom:1px solid #dce7ec} @media print{.notice{border:2px solid #c69843}}</style><h1>'+title+'</h1>'+body+'</html>'
