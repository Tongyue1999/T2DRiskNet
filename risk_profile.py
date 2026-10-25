"""Five explicit cumulative prediction windows, shared by local and public UI."""
from datetime import date, timedelta
from html import escape
import math

HORIZONS = [3, 6, 12, 36, 60]

def profile_html(row, model='02', lang='zh'):
    zh = lang == 'zh'
    assessment = date.fromisoformat(str(row['assessment_date'])[:10])
    cards = []
    for h in HORIZONS:
        risk = float(row[f'risk_{model}_{h}'])
        if not math.isfinite(risk) or not 0 <= risk <= 1:
            raise ValueError('Invalid risk probability')
        end = assessment + timedelta(days=h*30)
        label = f'未来 {h} 个月' if zh else f'Within {h} months'
        badge=('待验证 · ' if zh else 'Unvalidated · ') if row.get('model_family')=='reduced' and h==60 else ''
        cards.append(f'<div class="risk-card"><div>{label}</div><strong>{risk:.1%}</strong><small>{badge}{h*30} '+('天 · 截至 ' if zh else 'days · through ')+f'{end}</small></div>')
    title = '首次复合心血管事件 · 累积预测风险' if zh else 'First composite cardiovascular event · cumulative predicted risk'
    note = '各窗口均从评估日开始；模型按每月30天计算。五个数值不能相加，也不是年化风险。随访时间由医生结合临床情况确认。' if zh else 'Every window starts at assessment; model months are 30 days. These probabilities are not additive or annualised. Follow-up timing requires clinical review.'
    return '''<style>.risk-panel{border:1px solid #dce5ed;border-radius:20px;background:linear-gradient(135deg,#f0faf9,#f7f9fd);padding:24px;margin:14px 0;color:#183247}.risk-kicker{font-size:12px;letter-spacing:2px;color:#087f8c}.risk-panel h3{margin:6px 0 12px;font-size:21px}.risk-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.risk-card{background:white;border:1px solid #dce9ed;border-radius:14px;padding:16px 12px}.risk-card strong{display:block;font-size:30px;color:#075b68;line-height:1.5}.risk-card small{display:block;font-size:11px;color:#526b79}.risk-note{font-size:13px;color:#526b79;margin-top:14px}@media(max-width:800px){.risk-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media print{.risk-panel{break-inside:avoid}.risk-card strong{font-size:23px}}</style>''' + f'<section class="risk-panel"><div class="risk-kicker">T2DRISKNET / MODEL {escape(model)}</div><h3>{title}</h3><p>'+('评估日期：' if zh else 'Assessment: ')+f'{assessment}</p><div class="risk-grid">'+''.join(cards)+f'</div><div class="risk-note">{note}</div></section>'

def render_profile(st, row, model='02', lang='zh'):
    st.markdown(profile_html(row, model, lang), unsafe_allow_html=True)
