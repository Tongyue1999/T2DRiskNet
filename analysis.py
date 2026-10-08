"""Capacity-constrained evaluation with marginal IPCW and paired bootstrap."""
import numpy as np
import pandas as pd

def check(frame, scores):
    required = ['patient_key', 'duration_days', 'event_type'] + list(scores)
    if any(c not in frame for c in required):
        raise ValueError('缺少患者标识、随访、事件类型或策略分数。')
    if frame.patient_key.isna().any() or frame.patient_key.duplicated().any():
        raise ValueError('每次分析必须每名患者一行，患者标识不能重复或缺失。')
    if not frame.event_type.isin([0,1,2]).all():
        raise ValueError('event_type 必须为 0 删失、1 CVD、2 竞争死亡。')
    values = frame[['duration_days'] + list(scores)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:,0] < 0).any():
        raise ValueError('随访或分数存在缺失、非有限值或负随访。')
    if ((frame.duration_days == 0) & (frame.event_type != 0)).any():
        raise ValueError('评估当日已有事件或死亡，不能用于首次事件预测分析。')

def event_weights(frame, horizon):
    """1/G(T-) for observed target events, with competing deaths NOT censored."""
    times = frame.duration_days.to_numpy(dtype=float)
    kinds = frame.event_type.to_numpy(dtype=int)
    order = np.argsort(times, kind='stable')
    sorted_times, sorted_kinds = times[order], kinds[order]
    unique, starts, counts = np.unique(sorted_times, return_index=True, return_counts=True)
    censor_counts = np.add.reduceat((sorted_kinds == 0).astype(float), starts)
    at_risk = len(times) - starts
    after = np.cumprod(1 - censor_counts / at_risk)
    before = np.r_[1., after[:-1]]
    lookup = dict(zip(unique, before))
    pos = np.searchsorted(unique, horizon, side='left') - 1
    support = 1. if pos < 0 else float(after[pos])
    targets = (kinds == 1) & (times <= horizon)
    weights = np.zeros(len(frame))
    for index in np.flatnonzero(targets):
        g = lookup[times[index]]
        if g <= 0:
            raise ValueError('事件时间的删失生存概率为零，无法估计。')
        weights[index] = 1 / g
    return weights, support, int(((kinds==0) & (times<horizon)).sum())

def selected(frame, column, fraction):
    k = max(1, min(len(frame), int(np.floor(len(frame)*fraction + 0.5))))
    order = np.lexsort((frame.patient_key.astype(str).to_numpy(), -frame[column].to_numpy(float)))
    mask = np.zeros(len(frame), dtype=bool)
    mask[order[:k]] = True
    return mask

def metrics(frame, column, fraction, weights):
    mask = selected(frame, column, fraction)
    k, tp, total = int(mask.sum()), float(weights[mask].sum()), float(weights.sum())
    valid = tp <= k + 1e-8 and tp <= len(frame) + 1e-8
    return {'strategy':column, 'capacity_pct':100*fraction, 'selected_n':k, 'reviews_per1000':1000*k/len(frame), 'captured_per1000':1000*tp/len(frame), 'non_event_reviews_per1000':1000*(k-tp)/len(frame) if valid else np.nan, 'capture_rate':tp/total if total>0 else np.nan, 'ppv':tp/k if valid else np.nan, 'miss_rate':1-tp/total if total>0 else np.nan, 'valid_probability_estimate':valid}

def evaluate(frame, scores, horizon_months, fractions=(.05,.1,.2), bootstrap=200):
    check(frame, scores)
    days = horizon_months * 30
    weights, support, censored = event_weights(frame, days)
    if not np.any(weights > 0):
        raise ValueError('该时间窗没有已观察到的目标 CVD 事件，无法评价事件捕获增益。风险预测仍可运行；资源验证需要有真实事件和随访的独立队列。')
    if support < .1:
        raise ValueError('该时间窗随访支持不足（G(t-) < 0.10），不输出获益估计；请选择较短时间窗。')
    table = pd.DataFrame([metrics(frame, col, frac, weights) for frac in fractions for col in scores])
    curve = pd.DataFrame([metrics(frame, col, frac, weights) for frac in np.arange(.01,.301,.01) for col in scores])
    comparisons = []
    if len(scores) >= 2:
        a,b = scores[:2]
        boot_values = {q:[] for q in fractions}
        rng = np.random.default_rng(20261006)
        valid_resamples = 0
        for _ in range(bootstrap):
            sampled = frame.iloc[rng.integers(0,len(frame),len(frame))].reset_index(drop=True)
            w, s, _ = event_weights(sampled, days)
            if s < .1:
                continue
            valid_resamples += 1
            for q in fractions:
                am, bm = selected(sampled,a,q), selected(sampled,b,q)
                boot_values[q].append(1000*float(w[am].sum()-w[bm].sum())/len(frame))
        for q in fractions:
            am,bm = selected(frame,a,q),selected(frame,b,q)
            diff = 1000*float(weights[am].sum()-weights[bm].sum())/len(frame)
            enough = len(boot_values[q]) >= max(50, .8*bootstrap)
            lo,hi = np.quantile(boot_values[q],[.025,.975]) if enough else (np.nan,np.nan)
            comparisons.append({'capacity_pct':100*q,'comparison':a+' vs '+b,'extra_captured_per1000':diff,'ci_low':lo,'ci_high':hi,'change_non_event_reviews_per1000':-diff,'added_patients':int((am & ~bm).sum()),'removed_patients':int((bm & ~am).sum()),'shared_patients':int((am & bm).sum()),'valid_bootstrap':valid_resamples})
    marginal = []
    for col in scores:
        previous = None
        for q in fractions:
            m = metrics(frame,col,q,weights)
            if previous:
                gain = m['captured_per1000']-previous['captured_per1000']
                extra = m['reviews_per1000']-previous['reviews_per1000']
                marginal.append({'strategy':col,'capacity_change':f"{previous['capacity_pct']:g}% → {q*100:g}%",'extra_reviews_per1000':extra,'extra_captured_per1000':gain,'reviews_per_extra_event':extra/gain if gain>0 else np.nan})
            previous = m
    return {'table':table,'curve':curve,'comparison':pd.DataFrame(comparisons),'marginal':pd.DataFrame(marginal),'quality':{'n':len(frame),'observed_target_events':int(((frame.event_type==1)&(frame.duration_days<=days)).sum()),'competing_deaths':int(((frame.event_type==2)&(frame.duration_days<=days)).sum()),'censored_before_horizon':censored,'censor_survival':support,'estimated_events_per1000':1000*weights.sum()/len(frame),'method':'Marginal IPCW; independent censoring assumption; competing death is an observed non-target outcome; paired patient bootstrap; 30 days/month.'}}
