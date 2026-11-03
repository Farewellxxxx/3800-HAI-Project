"""Replay an exported session revision. Never overwrites an output directory."""
import argparse
import base64
import json
from pathlib import Path

from jammate.web_session import replay_revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fluidsynth', type=Path)
    parser.add_argument('--soundfont', type=Path)
    args = parser.parse_args()
    if bool(args.fluidsynth) != bool(args.soundfont):
        parser.error('provide both --fluidsynth and --soundfont, or neither for the built-in renderer')
    if args.out.exists():
        parser.error('output directory already exists; choose a new path')
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    result = replay_revision(receipt, fluidsynth=args.fluidsynth, soundfont=args.soundfont)
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ['wav', 'midi']:
        (args.out/('band.'+('mid' if name=='midi' else name))).write_bytes(base64.b64decode(result.pop(name)))
    (args.out/'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Replayed {result["bars"]} bars at {result["tempo_bpm"]} BPM into {args.out}')


if __name__ == '__main__':
    main()
