<div align="center">
  <img src="docs/assets/logo_placeholder.png" alt="LoRaLink-MLLC logo" width="120" />
  <h1>LoRaLink-MLLC</h1>
  <p><strong>LoRa UART(P2P) 링크에서 ML 기반 손실 압축으로 페이로드(payload)를 줄이고, 링크/정보 보존 지표를 현장에서 검증하는 실험 런타임.</strong></p>

  <p>
    <a href="https://github.com/Hmeon/LoRa-Project/actions/workflows/ci.yml"><img alt="ci" src="https://github.com/Hmeon/LoRa-Project/actions/workflows/ci.yml/badge.svg?branch=main" /></a>
    <img alt="coverage" src="https://img.shields.io/badge/coverage-100%25-brightgreen" />
    <img alt="python" src="https://img.shields.io/badge/python-%3E%3D3.10-blue" />
    <img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-blue" />
    <img alt="radio" src="https://img.shields.io/badge/radio-SX1262%20(E22--900T22S)-informational" />
    <img alt="link" src="https://img.shields.io/badge/link-UART-yellow" />
  </p>

  <p>
    <a href="START_HERE.md">Start Here</a> ·
    <a href="#quickstart-5-min-mock">Quickstart</a> ·
    <a href="docs/01_design_doc_experiment_plan.md">Design Doc</a> ·
    <a href="docs/runbook_uart_sensing.md">Field Runbook</a> ·
    <a href="docs/reproducibility.md">Reproducibility</a> ·
    <a href="CONTRIBUTING.md">Contributing</a> ·
    <a href="SECURITY.md">Security</a>
  </p>
</div>

README는 “랜딩 + 매뉴얼 + 협업 계약서” 역할을 합니다. 상세 설계/런북/스펙은 [docs/](docs/)에 분리돼 있으며, 본 README는 단일 진입점(hub)입니다.

<details>
<summary><strong>Table of Contents</strong></summary>

- [What is LoRaLink-MLLC?](#what-is-loralink-mllc)
- [Key Features](#key-features)
- [Non-goals](#non-goals)
- [Architecture](#architecture)
- [Quickstart (5 min, mock)](#quickstart-5-min-mock)
- [Usage](#usage)
- [Configuration](#configuration)
- [Reproducibility](#reproducibility)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Security](#security)
- [Support](#support)
- [License](#license)
- [Citation](#citation)

</details>

## What is LoRaLink-MLLC?
LoRaLink-MLLC는 **E22-900T22S(SX1262) AT UART P2P** 환경에서 **페이로드(payload) 크기 감소**가
링크 지표(**PDR/ETX/ToA/에너지**)와 정보 보존(**재구성 MAE/MSE**)에 미치는 영향을 **재현 가능**하게 검증하기 위한 실험 런타임입니다.

핵심 설계 조건(고정):
- **Packet format**: `LEN(1B) | SEQ(1B) | PAYLOAD(LEN bytes)` (`PAYLOAD <= 238B`) — [docs/protocol_packet_format.md](docs/protocol_packet_format.md)
- **No AUX** 전제: TX pacing/ACK timeout은 **ToA 추정 + guard_ms**로 운용 — [docs/toa_estimation.md](docs/toa_estimation.md)
- **On-air payload는 바이너리**(JSON 전송 금지). JSON/YAML은 설정/로그/데이터셋에만 사용 — [docs/sensing_pipeline.md](docs/sensing_pipeline.md)

## Key Features
- **단일 계약(Contract) 기반 실험**: RunSpec(YAML/JSON) + Artifacts manifest + JSONL logs로 재현성 고정
- **RAW baseline 제공**: `sensor12_packed`(30B/step; gps f32 + IMU/rpy i16 fixed-point)
- **Payload-size baseline 제공**: `sensor12_packed_truncate`(32/16/8B 등)로 “학습 없이 잘라서 보내기” 대비 가능
- **BAM inference codec**: 아티팩트 로딩(`bam_manifest.json`, `layer_*.npz`, `norm.json`) 기반 LATENT 송수신
- **현장 실행 워크플로**: Phase 0~4 런북 + 리포트/플롯/검증/패키징 스크립트 포함
- **관측 가능성**: ACK RTT/queue/e2e, codec CPU cost(proxy), RSSI(옵션)까지 로그/metrics로 일관 출력
- **고품질 테스트**: `pytest` + 100% coverage (CI로 강제)

## Non-goals
- 이 repo는 **E22 AT UART P2P**만 대상으로 하며, MAC/네트워크 계층을 구현하지 않습니다.
- 모듈(주소/채널/air speed/CRC/헤더/LDRO 등) 설정은 **런타임에서 자동화하지 않습니다**. 외부에서 설정하고 기록합니다(보조: [scripts/e22_tool.py](scripts/e22_tool.py)).
- 전력 측정은 외부 장비/방법에 의존합니다(Phase 4는 측정값 결합 및 파생 지표 계산 도구만 제공).

## Architecture
```mermaid
flowchart LR
  subgraph TX[TX node]
    Sensor[Sensor window] --> Encode["Codec: RAW / Truncate / Zlib / BAM"]
    Encode --> Packetize["Packetize LEN│SEQ│PAYLOAD"]
    Packetize --> UART_TX["UART → E22"]
    UART_TX --> LogTX["JSONL log (+ optional dataset_raw.jsonl)"]
  end

  UART_TX --> Air[LoRa air link]

  subgraph RX[RX node]
    Air --> UART_RX["UART ← E22"]
    UART_RX --> Parse[Parse frame]
    Parse --> Decode[Decode / reconstruct (LATENT)]
    Decode --> LogRX[JSONL log]
  end

  subgraph Offline[Offline training loop (Phase 2)]
    Data[dataset_raw.jsonl] --> Train[Train BAM-family model]
    Train --> Artifacts[Artifacts: layer_*.npz + norm.json + bam_manifest.json]
  end

  Artifacts -.-> Encode
  Artifacts -.-> Decode
```

## Quickstart (5 min, mock)
하드웨어 없이 mock 링크로 “패킷화 → 로깅 → metrics” 성공 경로를 검증합니다.

### Prerequisites
- Python **3.10+**

### Install
```bash
python -m pip install -e .
```

### Run (Phase 0/1)
```bash
python -m loralink_mllc.cli phase0 --sweep configs/examples/sweep.json --out out/c50.json
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/examples/raw.json --latent configs/examples/latent.json --out out/report.json
```
생성물:
- `out/c50.json` (mock C50 선택 결과)
- `out/report.json` (RAW vs LATENT 비교 요약)
- `out/phase0/`, `out/phase1/` (JSONL 로그)

### Verify (metrics)
```bash
python -m loralink_mllc.cli metrics --log out/phase1/*_tx.jsonl --out out/phase1/metrics.json
```

## Usage
### 1) UART (실장비) 송수신
모듈 설정은 외부에서 완료해야 하며, UART 모드는 `pyserial`이 필요합니다.
```bash
python -m pip install -e .[uart]

# RX
python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600

# TX
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```

RSSI byte output(REG3 bit 7)을 켰다면 프레임 파싱이 어긋나는 것을 방지하기 위해 TX/RX 모두에 `--uart-rssi-byte`를 추가하세요.
관련: [docs/runbook_uart_sensing.md](docs/runbook_uart_sensing.md), [docs/radio_constraints_e22.md](docs/radio_constraints_e22.md)

### 2) 센서 입력(JSONL/CSV) + dataset 기록
센서 입력 스키마: [docs/sensing_pipeline.md](docs/sensing_pipeline.md)
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --sampler jsonl \
  --sensor-path configs/examples/sensor_sample.jsonl \
  --dataset-out out/dataset_raw.jsonl \
  --radio mock
```

### 3) Phase 2: BAM 학습(오프라인) → 아티팩트 생성
```bash
python -m pip install -e .[bam]

python scripts/phase2_train_bam.py \
  --dataset out/dataset_raw.jsonl \
  --out-dir models/<model_id> \
  --hidden-dims 24,16 \
  --latent-dim 16 \
  --packing int16 \
  --train-ratio 0.8 \
  --split-seed 0
```
설계/계약: [docs/phase2_bam_training.md](docs/phase2_bam_training.md), [docs/bam_codec_artifacts.md](docs/bam_codec_artifacts.md)

### 4) Phase 3/4: 리포트/플롯/KPI
- Phase 3 리포트(로그 + dataset join + roundtrip recon): `scripts/phase3_report.py`
- Phase 4 에너지 결합: `scripts/phase4_energy_report.py`
- KPI 체크: `scripts/kpi_check.py`

현장 런북:
- `docs/phase3_on_air_validation.md`
- `docs/phase4_energy_evaluation.md`

## Configuration
핵심 설정 단위는 **RunSpec**(YAML/JSON)입니다: `loralink_mllc/config/runspec.py`

자주 만지는 값(요약):
- `phy.*`: `sf`/`bw_hz`/`cr`/`crc_on`/`explicit_header`/`preamble`/`ldro`/`tx_power_dbm` (ToA 추정 입력)
- `window.*`: `dims=12`, `W/stride/sample_hz` (데이터셋/모델/코덱과 반드시 일치)
- `codec.*`: `sensor12_packed`, `sensor12_packed_truncate`, `zlib`, `bam` 등
- `tx.*`: `guard_ms`, `ack_timeout_ms`(auto 지원), `max_retries`, `max_windows`
- `max_payload_bytes`: 기본 238(E22 UART P2P 240B 제한에서 2B 헤더 제외; `LEN <= 238`)

참고:
- PHY profile(ADR-CODE) 테이블: [configs/examples/phy_profiles.yaml](configs/examples/phy_profiles.yaml) / [docs/phy_profiles_adr_code.md](docs/phy_profiles_adr_code.md)
- AT Air Speed preset ↔ PHY 매핑은 **펌웨어 버전 기준으로 확정/고정**해야 합니다.

## Reproducibility
재현 가능한 1회 run의 최소 패키지(권장):
- RunSpec(TX/RX), Artifacts manifest, TX/RX JSONL logs
- (학습/재구성 평가 시) `dataset_raw.jsonl`, BAM 아티팩트(`layer_*.npz`, `norm.json`, `bam_manifest.json`)
- UART/C50/Phase 기록 템플릿(실측 기록): `configs/examples/*.yaml`

도구:
- 실행 산출물 조인/검증: [scripts/validate_run.py](scripts/validate_run.py)
- 해시 포함 아카이빙/zip: [scripts/package_run.py](scripts/package_run.py)

## Documentation
진짜 “소스 오브 트루스”는 설계 문서입니다:
- [docs/01_design_doc_experiment_plan.md](docs/01_design_doc_experiment_plan.md) (packet/log/phase의 단일 기준)

<details>
<summary><strong>Docs map (expanded)</strong></summary>

- Start here: [START_HERE.md](START_HERE.md)
- Protocol: [docs/protocol_packet_format.md](docs/protocol_packet_format.md)
- Radio constraints (E22): [docs/radio_constraints_e22.md](docs/radio_constraints_e22.md)
- ToA estimation: [docs/toa_estimation.md](docs/toa_estimation.md)
- PHY profiles (ADR-CODE): [docs/phy_profiles_adr_code.md](docs/phy_profiles_adr_code.md), [configs/examples/phy_profiles.yaml](configs/examples/phy_profiles.yaml)
- Sensing schema: [docs/sensing_pipeline.md](docs/sensing_pipeline.md)
- UART + sensing runbook: [docs/runbook_uart_sensing.md](docs/runbook_uart_sensing.md)
- Reproducibility checklist: [docs/reproducibility.md](docs/reproducibility.md)
- Phase runbooks: [docs/phase0_c50_field.md](docs/phase0_c50_field.md), [docs/phase1_dataset_collection.md](docs/phase1_dataset_collection.md), [docs/phase2_bam_training.md](docs/phase2_bam_training.md), [docs/phase3_on_air_validation.md](docs/phase3_on_air_validation.md), [docs/phase4_energy_evaluation.md](docs/phase4_energy_evaluation.md)
- Review checklist: [docs/review_checklist.md](docs/review_checklist.md)
- Patch notes: [docs/patch_notes.md](docs/patch_notes.md)
- Papers dissected: [docs/papers/](docs/papers/)

</details>

## Roadmap
Field completion (Phase 0~4) 기준으로 남은 핵심 항목:
- **Air Speed preset ↔ PHY 매핑 확정**(타겟 펌웨어 버전 고정) + `configs/examples/uart_record.yaml`에 기록
- **실험 상수 고정**: `guard_ms`, `window.W/stride/sample_hz`, ACK 정책(채널 포함), 측정 장비/방법
- **Phase 3/4 실측 실행** → `report_all.json`/플롯 생성 → KPI 산출 및 README/README.ko.md 결과 섹션 업데이트
- **Release hygiene**: `CITATION.cff` TODO 채우기, 릴리즈 태그/CHANGELOG 관리

## Troubleshooting
- `requires-python` 오류: Python 3.10+ 환경인지 확인 후 재설치
- `PyYAML is required ...`: `pip install -e .`가 정상인지 확인(의존성에 PyYAML 포함)
- UART 모드에서 `pyserial is required`: `pip install -e .[uart]` 필요
- RX에 `rx_parse_fail`가 많음: UART 스트림이 순수 `LEN|SEQ|PAYLOAD` 형식이 아닐 가능성(특히 RSSI byte output 켠 경우 `--uart-rssi-byte` 필수)
- ACK가 오지 않음: 주소/채널/baud/air speed 불일치 또는 RX 미기동(현장 기록 템플릿으로 점검)
- BAM 로딩 실패: `bam_manifest.json` 경로/`model_path`/`layer_*.npz`/`norm.json` 누락 또는 window 설정 불일치

## Contributing
- 개발 환경/규칙: [CONTRIBUTING.md](CONTRIBUTING.md)
- 커뮤니티 규범: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## Security
보안 취약점 제보는 공개 이슈로 받지 않습니다. [SECURITY.md](SECURITY.md)를 따라주세요.

## Support
지원/문의/버그 리포트 가이드: [SUPPORT.md](SUPPORT.md)

## License
Apache License 2.0. See [LICENSE](LICENSE).

참고: 제3자 명칭/상표 및 레퍼런스된 벤더 문서의 권리는 각 소유자에게 있으며, Apache-2.0의 적용 범위에 포함되지 않습니다. [NOTICE](NOTICE)를 참고하세요.

## Citation
연구/보고서에 사용 시 인용 정보: [CITATION.cff](CITATION.cff)
