"""Reproducible synthetic input benchmark; NOT human accuracy evidence."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import soundfile as sf

from jammate.analysis.rhythm import analyze_rhythm_audio
from jammate.contracts.adapters import from_rhythm, from_text


def waveform(kind, bpm, *, jitter=0., gain=1., seed=3800):
    sr, expected = 22050, [0., 1., 1.5, 3.]
    beat = 60/bpm
    origin = .2+4*beat
    times = [.2+i*beat for i in range(4)] + [origin+b*beat for b in expected]
    rng = np.random.default_rng(seed)
    audio = np.zeros(round((origin+4*beat+.15)*sr), dtype=np.float32)
    for index, onset in enumerate(times):
        if index>=4:
            onset += rng.uniform(-jitter,jitter)
        t = np.arange(round(.10*sr))/sr
        noise = rng.standard_normal(len(t))
        if kind=='clap_like': pulse=noise*np.exp(-t/0.018)
        elif kind=='snap_like': pulse=noise*np.exp(-t/.006)*np.sin(2*np.pi*2800*t)
        elif kind=='tap_like': pulse=np.sin(2*np.pi*320*t)*np.exp(-t/.018)
        else: pulse=(np.sin(2*np.pi*100*t)+.3*noise)*np.exp(-t/.028)
        pulse = pulse/(max(abs(pulse))+1e-8)*.7*gain
        start=round(onset*sr)
        audio[start:start+len(pulse)] += pulse
    return audio, sr, expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('examples/input_mrt2/benchmark'))
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    report={'evidence':'synthetic_waveforms_only_not_human_accuracy',
            'success_definition':'valid event, tempo error <= 3 BPM, exact 1/16-grid pattern',
            'limitations':['one complete 4/4 bar','steady four-hit count-in','60–180 BPM',
                           'straight 1/16 quantization; swing/microtiming not represented',
                           'confidence is uncalibrated grid alignment, not correctness probability'],
            'rhythm':[],'negative_cases':[],'text':[]}
    for kind in ['clap_like','snap_like','tap_like','beatbox_like']:
        for bpm in [80,100,140]:
            name=f'{kind}_{bpm}'
            audio,sr,expected=waveform(kind,bpm)
            sf.write(args.out/(name+'.wav'),audio,sr)
            start=time.perf_counter()
            try:
                context=analyze_rhythm_audio(audio,sr,count_in=4)
                elapsed=time.perf_counter()-start
                event=from_rhythm(context,session_id='benchmark_'+name,event_id='evt_'+name,
                    audio_duration_s=len(audio)/sr,started_at=0,tempo_source='detected',
                    confidence_kind='grid_alignment_heuristic').to_dict()
                (args.out/(name+'.input-event.json')).write_text(json.dumps(event,indent=2)+'\n',encoding='utf-8')
                error=abs(context.tempo_bpm-bpm)
                predicted=list(context.onset_beats)
                matched=len(set(expected)&set(predicted))
                report['rhythm'].append({'case':name,'expected_bpm':bpm,'detected_bpm':context.tempo_bpm,
                    'tempo_absolute_error':error,'expected_beats':expected,'detected_beats':predicted,
                    'grid_hit_f1':2*matched/(len(expected)+len(predicted)),
                    'grid_alignment_heuristic':context.confidence,'perception_s':elapsed,
                    'cold_first_call':len(report['rhythm'])==0,'passed':error<=3 and predicted==expected})
            except ValueError as exc:
                report['rhythm'].append({'case':name,'passed':False,'error':str(exc)})
    for name,audio in [('silence',np.zeros(132300)),('incomplete',waveform('clap_like',100)[0][:60000])]:
        try:
            analyze_rhythm_audio(audio,22050,count_in=4)
            report['negative_cases'].append({'case':name,'rejected':False})
        except ValueError as exc:
            report['negative_cases'].append({'case':name,'rejected':True,'error':str(exc)})
    for index,text in enumerate(['  来一段，慢一点\n','这个不错，鼓再猛一点','我给你个节奏','warm lo-fi 🎵\n保持这个']):
        event=from_text(text,session_id='benchmark_text',event_id=f'evt_text_{index}').to_dict()
        report['text'].append({'exact_original_preserved':event['payload']['text']==text,
                               'source':event['source'],'confidence':event['confidence']})
    report['rhythm_passed']=sum(row['passed'] for row in report['rhythm'])
    report['rhythm_total']=len(report['rhythm'])
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['evidence','rhythm_passed','rhythm_total','negative_cases']},ensure_ascii=False))


if __name__=='__main__':
    main()
