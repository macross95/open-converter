"""Command-line interface."""

import argparse
import json
import os
import sys

from ..core.converter import Converter
from ..core.jobs import JobQueue, JobResult
from ..presets.defaults import PRESETS


def _parse_transforms(args):
    transforms = []
    if args.resize:
        w, h = (args.resize + "x").split("x")[:2]
        transforms.append({"resize": {"width": int(w) if w else None, "height": int(h) if h else None, "fit": args.fit}})
    if args.crop:
        parts = args.crop.split(",")
        transforms.append({"crop": {"left": int(parts[0]), "top": int(parts[1]), "width": int(parts[2]), "height": int(parts[3])}})
    if args.rotate is not None:
        transforms.append({"rotate": {"angle": args.rotate, "expand": True}})
    if args.flip:
        transforms.append({"flip": {"direction": args.flip}})
    if args.grayscale:
        transforms.append({"grayscale": {}})
    return transforms


def cmd_convert(args):
    conv = Converter(concurrency=args.workers)
    transforms = _parse_transforms(args)
    try:
        res = conv.convert(
            args.input, args.output,
            format=args.format,
            quality=args.quality,
            transforms=transforms,
            metadata=args.metadata,
            preset=args.preset,
        )
        print(json.dumps(res, indent=2) if args.json else f"OK: {res['input']} -> {res['output']} ({res['size']} bytes, {res['duration_ms']} ms)")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_batch(args):
    conv = Converter(concurrency=args.workers)
    os.makedirs(args.output, exist_ok=True)
    exts = {e.lower() for e in conv.registry.supported_extensions()}
    files = []
    for root, _, fnames in os.walk(args.input):
        for fn in sorted(fnames):
            if os.path.splitext(fn)[1].lower() in exts:  # solo imágenes
                files.append(os.path.join(root, fn))
    items = [{"input": f, "output": os.path.join(args.output, os.path.splitext(os.path.basename(f))[0] + "." + args.format.lstrip("."))} for f in files]

    def worker(item):
        t0 = __import__("time").time()
        try:
            res = conv.convert(item["input"], item["output"], format=args.format, quality=args.quality, metadata=args.metadata, preset=args.preset)
            return JobResult(input_path=item["input"], output_path=item["output"], ok=True, duration_ms=int((__import__("time").time()-t0)*1000), warnings=res.get("warnings", []))
        except Exception as e:
            return JobResult(input_path=item["input"], ok=False, error=str(e), duration_ms=int((__import__("time").time()-t0)*1000))

    q = JobQueue(workers=args.workers)

    def on_progress(done, total, r):
        status = "OK" if r.ok else "FAIL"
        print(f"[{done}/{total}] {status}: {os.path.basename(r.input_path)}", flush=True)

    results = q.run_batch(items, worker, on_progress=on_progress)
    q.shutdown()
    ok = sum(1 for r in results if r.ok)
    print(f"\nDone: {ok}/{len(results)} succeeded")
    return 0 if ok == len(results) else 1


def cmd_info(args):
    conv = Converter()
    try:
        info = conv.info(args.input)
        print(json.dumps(info, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_formats(args):
    conv = Converter()
    print(json.dumps({"input_formats": conv.supported_formats(), "output_formats": conv.supported_output_formats()}, indent=2))
    return 0


def cmd_presets(args):
    print(json.dumps(PRESETS, indent=2))
    return 0


def cmd_gui(args):
    from ..single_instance import ensure_single_instance
    if not ensure_single_instance():
        return 0
    from ..gui.tk_app import run_gui
    run_gui()
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:  # sin argumentos: abrir la ventana
        argv = ["gui"]
    parser = argparse.ArgumentParser(prog="openconverter", description="Open Converter: convertidor de imágenes multi-formato")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("convert", help="Convert a single image")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--format", "-f", default=None)
    p.add_argument("--quality", "-q", type=int, default=90)
    p.add_argument("--resize", default=None, help="WxH, e.g. 1920x1080")
    p.add_argument("--fit", default="inside", choices=["inside", "cover", "exact"])
    p.add_argument("--crop", default=None, help="left,top,width,height")
    p.add_argument("--rotate", type=float, default=None)
    p.add_argument("--flip", choices=["horizontal", "vertical"], default=None)
    p.add_argument("--grayscale", action="store_true")
    p.add_argument("--metadata", default="preserve", choices=["preserve", "strip", "selective"])
    p.add_argument("--preset", default=None, choices=list(PRESETS.keys()))
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("batch", help="Batch convert a directory")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--format", "-f", required=True)
    p.add_argument("--quality", "-q", type=int, default=90)
    p.add_argument("--metadata", default="preserve", choices=["preserve", "strip", "selective"])
    p.add_argument("--preset", default=None, choices=list(PRESETS.keys()))
    p.add_argument("--workers", type=int, default=None)
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("info", help="Show image info")
    p.add_argument("input")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("formats", help="List supported formats")
    p.set_defaults(func=cmd_formats)

    p = sub.add_parser("presets", help="List presets")
    p.set_defaults(func=cmd_presets)

    p = sub.add_parser("gui", help="Launch GUI")
    p.set_defaults(func=cmd_gui)

    args = parser.parse_args(argv)
    if args.command == "batch" and args.workers is None:
        args.workers = 4
    if args.command == "convert" and args.workers is None:
        args.workers = 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
