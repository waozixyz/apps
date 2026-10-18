"""Link actual Apps and DaochiClient against an explicit canonical Crypto source.

No package checkout, generated-code patch or consumer lock edit is involved.
The independent fixture uses real package-qualified imports on retained IR55.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "fixtures/crypto_consumer"
WORK = ROOT / "build/crypto-consumer-test"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--crypto-source", type=Path, required=True)
    parser.add_argument("--daochi-source", type=Path, required=True)
    args = parser.parse_args()
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS"):
        os.environ.pop(name, None)
    mapping_rows = (ROOT / "build/.ziran/module-map.tsv").read_text().splitlines()
    lines = ["P\troot\t" + str(CONSUMER), "M\troot\tmain\t" + str(CONSUMER / "main.zi")]
    package = "p0000000000000001"
    crypto_id = next(row.split("\t")[3] for row in mapping_rows if row.startswith("D\troot\tcrypto/sha256\t"))
    old_crypto = next(row.split("\t")[2] for row in mapping_rows if row.startswith("P\t" + crypto_id + "\t"))
    for row in mapping_rows:
        fields = row.split("\t")
        if len(fields) > 1 and fields[1] == "root":
            fields[1] = package
        fields = [str(args.crypto_source.resolve()) + field[len(old_crypto):] if field == old_crypto or field.startswith(old_crypto + "/") else field for field in fields]
        lines.append("\t".join(fields))
    for name, filename in tomllib.loads((ROOT / "ziran.toml").read_text())["exports"].items():
        lines.append(f"D\troot\tapps/{name}\t{package}\t{Path(filename).stem}")
    lines.append(f"D\troot\tcrypto/sha256\t{crypto_id}\tsha256")
    dao_id = "p0000000000000002"
    lines += [f"P\t{dao_id}\t{args.daochi_source.resolve()}",
              f"M\t{dao_id}\tcrypto\t{args.daochi_source.resolve() / 'crypto.zi'}",
              f"D\troot\tdaochi_client/crypto\t{dao_id}\tcrypto"]
    WORK.mkdir(parents=True, exist_ok=True)
    mapping = WORK / "module-map.tsv"
    mapping.write_text("\n".join(lines) + "\n")
    toolchain = Path(subprocess.check_output([str(ROOT / "scripts/ziran.sh"), "pkg", "path", "ziran"], cwd=ROOT, text=True).strip())
    output = WORK / "c"
    subprocess.run([str(toolchain / "build/bin/zi2c"), "--prune-stale", "--no-main", "--entry", "main:Check",
                    "--module-path", str(toolchain / "std"), "--root", str(CONSUMER), "-o", str(output),
                    str(CONSUMER / "main.zi")], cwd=ROOT,
                   env=os.environ | {"ZIRAN_PACKAGE_MAP": str(mapping)}, check=True)
    (output / "entry.c").write_text('#include "main.h"\nint main(void) { return Check(); }\n')
    includes = [arg for path in [output, *sorted(output.rglob('*'))] if path.is_dir() for arg in ("-iquote", str(path))]
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O2", "-ffunction-sections", "-fdata-sections",
                    "-I" + str(toolchain / "include"), *includes, *map(str, sorted(output.rglob("*.c"))),
                    str(args.runtime.resolve()), "-Wl,--gc-sections", "-lm", "-lpthread", "-o", str(WORK / "test")], check=True)
    subprocess.run([str(WORK / "test")], check=True)
    print("IR55 external Apps + DaochiClient + Crypto native link and unchanged SHA256/hex/HMAC APIs passed")


if __name__ == "__main__":
    main()
