# CleanYourMac-AI

**Reclaim RAM & cache bloat on any Mac/Linux laptop — then run a 0-GPU Offline AI in the freed memory.**

Powered by [MYCA-Modchip](https://github.com/brienteth/myca-ghr-modchip) (`78+ tok/s` pure CPU C99 + SIMD, `69 MB` footprint, zero cloud calls).

## Quick Start

```bash
git clone https://github.com/brienteth/cleanyourmac-ai.git
cd cleanyourmac-ai
python3 cleanyourmac.py
# Open http://127.0.0.1:8787/
```

### CLI Scan Mode

```bash
python3 cleanyourmac.py --scan
```

### Optional: Install the 0-GPU Offline AI Engine

```bash
curl -fsSL https://raw.githubusercontent.com/brienteth/myca-ghr-modchip/main/install.sh | sh
myca-modchip pull smollm2-135m
```

## Features
- **Live RAM & Process Audit:** Inspects real `vm_stat` / `/proc/meminfo` and top memory hogs.
- **Safe Cache Scanner:** Measures reclaimable user/npm/pip caches without deleting anything unexpectedly.
- **Built-in 0-GPU Offline AI:** Runs `myca-modchip` directly inside the dashboard with zero subscriptions.

## License
MIT
