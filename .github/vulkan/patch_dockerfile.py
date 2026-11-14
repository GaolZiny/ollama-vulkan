#!/usr/bin/env python3
"""Patch upstream ollama's Dockerfile into a slim, Vulkan-only amd64 image.

Upstream already builds a Vulkan llama-server variant and ships it in the
official image, together with CUDA 12/13, ROCm and MLX(CUDA) payloads. This
script keeps only the CPU + Vulkan payloads so the image is small and the
build fits on a standard GitHub-hosted runner:

  * base-amd64: the multi-GB rocm/dev-almalinux image is replaced by plain
    almalinux:8 with the same gcc-toolset-13 toolchain (dnf stays usable,
    so every downstream stage keeps working unchanged).
  * amd64 assembly stage: only llama-server-cpu and llama-server-vulkan
    are copied; CUDA / MLX stages are no longer referenced, so BuildKit
    never builds them.
  * amd64-archive: the ROCm payload is dropped.

The version is injected with the GOFLAGS build-arg (same as upstream's
release workflow), so the Go build stage is left untouched.

The script is strict on purpose: if upstream restructures the Dockerfile
again it exits non-zero with a clear message instead of producing a
silently broken build.

Usage: patch_dockerfile.py [path/to/Dockerfile]
"""

import re
import sys

KEEP_IN_AMD64 = {"llama-server-cpu", "llama-server-vulkan"}

BASE_AMD64 = """\
FROM --platform=linux/amd64 almalinux:8 AS base-amd64
RUN dnf install -y yum-utils epel-release \\
    && dnf install -y ccache git xz python3 \\
        gcc-toolset-13-gcc gcc-toolset-13-gcc-c++ gcc-toolset-13-binutils \\
    && dnf clean all
ENV PATH=/opt/rh/gcc-toolset-13/root/usr/bin:$PATH

"""

FROM_RE = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?\s*$", re.I)
COPY_FROM_RE = re.compile(r"^COPY\s+--from=(\S+)\s", re.I)


def fail(msg):
    sys.exit(f"patch_dockerfile: {msg}\n"
             "Upstream Dockerfile layout changed; update .github/vulkan/patch_dockerfile.py")


def split_stages(lines):
    """Return (preamble, [(name, [lines])]) where each stage starts at its FROM line."""
    preamble, stages = [], []
    for line in lines:
        m = FROM_RE.match(line)
        if m:
            stages.append([m.group(2), [line]])
        elif stages:
            stages[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, stages


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "Dockerfile"
    with open(path) as f:
        lines = f.readlines()

    preamble, stages = split_stages(lines)
    names = [n for n, _ in stages]
    for required in ("base-amd64", "base", "vulkan-deps", "llama-server-cpu",
                     "llama-server-vulkan", "build", "amd64", "amd64-archive"):
        if required not in names:
            fail(f"expected stage '{required}' not found")

    out = list(preamble)
    for name, body in stages:
        if name == "base-amd64":
            out.append(BASE_AMD64)
            continue

        if name in ("amd64", "amd64-archive"):
            kept = [body[0]]
            for line in body[1:]:
                m = COPY_FROM_RE.match(line)
                src = m.group(1) if m else None
                if src is None:
                    kept.append(line)
                elif name == "amd64" and src in KEEP_IN_AMD64:
                    kept.append(line)
                elif name == "amd64-archive" and src == "amd64":
                    kept.append(line)
                else:
                    kept.append("# [vulkan-only] " + line)
            body = kept

        out.extend(body)

    # Sanity check: the final amd64 stage must still pull in both payloads.
    text = "".join(out)
    for src in KEEP_IN_AMD64:
        if not re.search(rf"^COPY --from={re.escape(src)}\s", text, re.M):
            fail(f"'COPY --from={src}' missing after patching")

    with open(path, "w") as f:
        f.write(text)
    print(f"patch_dockerfile: patched {path} for Vulkan-only amd64 build")


if __name__ == "__main__":
    main()
