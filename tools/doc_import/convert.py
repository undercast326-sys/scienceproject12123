"""Read every .doc in a folder: {path: (tokens, {storage: latex})}."""
import glob
import re

from docparse import Doc
import mtef


def convert_folder(src):
    docs = {}
    for f in sorted(glob.glob(src.rstrip('/') + '/*.doc')):
        d = Doc(f)
        tokens = d.tokens()
        eqs = {}
        for sid in set(re.findall(r'\x00EQ:(_\d+)\x00', tokens)):
            data = d.equation_native(sid)
            if data is None:
                continue
            try:
                eqs[sid] = mtef.to_latex(data)[0]
            except (mtef.ParseError, mtef.Unsupported):
                pass
        docs[f] = (tokens, eqs)
    return docs
