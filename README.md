# LoRaLink-MLLC

LPWA 환경의 LoRa(P2P UART) 통신에서 시계열 센서 윈도우를 **ML 기반 손실 압축(BAM/FEBAM 계열)** 으로 인코딩해 **페이로드를 줄이고**, 그 영향(PDR/ETX/ToA/에너지, 재구성 오차)을 검증하는 실험 런타임이다.

Quick Links: [빠른 시작](#빠른-시작-mock) · [START_HERE.md](START_HERE.md) · [docs/01_design_doc_experiment_plan.md](docs/01_design_doc_experiment_plan.md) · [docs/sensing_pipeline.md](docs/sensing_pipeline.md) · [docs/runbook_uart_sensing.md](docs/runbook_uart_sensing.md) · [docs/phase2_bam_training.md](docs/phase2_bam_training.md) · [docs/phase3_on_air_validation.md](docs/phase3_on_air_validation.md) · [docs/phase4_energy_evaluation.md](docs/phase4_energy_evaluation.md)

## 개요
- Goal: payload 크기 변화(코덱/latent_dim/packing)가 링크 지표(PDR/ETX/ToA/에너지)와 정보 보존(재구성 MAE/MSE)에 미치는 영향을 실측/재현 가능한 형태로 검증한다.
- Problem: AUX 없는 E22 UART 환경에서 ToA를 추정해야 하며, 바이너리 payload(238B 제한) 내에서 window/latent를 설계해야 한다.
- Solution: `LEN|SEQ|PAYLOAD` 프레임 + RunSpec 기반 설정 + JSONL 로깅 + codec 실험(Phase 0/1/2/3/4 보조 스크립트)으로 비교 가능한 데이터를 만든다.
- Scope: Python 런타임, LoRa P2P UART(mock 포함), JSONL/CSV 센서 입력, RAW 바이너리 baseline(`sensor12_packed`), BAM inference artifacts 로딩을 포함한다.
- Non-goals: 런타임에서 E22 설정(AT 구성)은 자동화하지 않는다(외부 설정 + `scripts/e22_tool.py` 보조); 전력 측정은 외부 장비에 의존(Phase 4는 리포트 결합 도구만); 실 센서 드라이버/보드 제어는 포함하지 않는다.

## TODO (미구현)
- E22 AT UART P2P 링크만 대상으로 한다(추가 MAC/네트워크 계층 구현 없음).
- cross-device E2E 지연(송신 센서 시각 → 수신 복원 시각) 측정은 클럭 동기화/정의가 필요하다.
- SNR 수집 경로(가능한 경우) 정리/구현.
- Air Speed 프리셋 ↔ (SF/BW/CR) 매핑의 벤더 확인.
- 릴리스 패키징(라이선스/보안/기여 문서 포함) 정리.

## 주요 기능
- 제공: RunSpec YAML/JSON 로딩·검증 및 `max_payload_bytes` 제약 적용.
- 제공: `LEN|SEQ|PAYLOAD` 프레이밍과 엄격한 파서 오류 타입.
- 지원: RAW, zlib, BAM inference 코덱과 payload schema hash.
- 제공: TX/RX 노드의 ACK/재시도, ToA 추정 게이팅, JSONL 로깅.
- 제공: mock 링크(손실/지연/패턴)와 Phase 0/1 실험 runner.
- 제공: JSONL/CSV 센서 샘플러와 `dataset_raw.jsonl` 기록.
- 제한: UART 전송은 최소 transport만 포함하며 모듈 설정은 외부에서 처리한다.

## 빠른 시작 (Mock)

### Prerequisites
- Python 3.11 (pyproject.toml 기준)
- 하드웨어 필요 없음 (mock 링크 사용)

### Install
```bash
python -m pip install -e .
```
- 기대 결과: `python -m loralink_mllc.cli --help`가 동작한다.
- 흔한 오류: `requires-python` 오류가 나면 Python 3.11 환경에서 다시 설치한다.

### Run
```bash
python -m loralink_mllc.cli phase0 --sweep configs/examples/sweep.json --out out/c50.json
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/examples/raw.json --latent configs/examples/latent.json --out out/report.json
```
- 기대 결과: `out/c50.json`, `out/report.json`, `out/phase0/`, `out/phase1/`가 생성된다.
- 흔한 오류: `FileNotFoundError: configs/examples/...`가 나면 repo root에서 실행한다.

### Verify
```bash
python -m loralink_mllc.cli metrics --log out/phase1/*_tx.jsonl --out out/phase1/metrics.json
```
- 기대 결과: `out/phase1/metrics.json`이 생성된다.
- 흔한 오류: 로그 파일이 없으면 Run 단계를 먼저 완료한다.

## 사용 예

### UART RAW 송수신 (실장비)
UART 전송은 최소 transport만 제공하며 모듈 설정은 외부에서 완료해야 한다. `pyserial`이 필요하다.
```bash
python -m pip install -e .[uart]

python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600

python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```
- 기대 결과: RX 로그에 `rx_ok`, TX 로그에 `ack_received`가 기록된다.

### JSONL 센서 입력 + dataset 기록
JSONL 스키마는 `docs/sensing_pipeline.md`에 정의돼 있다.
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts_sensor12_packed.json \
  --sampler jsonl \
  --sensor-path configs/examples/sensor_sample.jsonl \
  --dataset-out out/dataset_raw.jsonl \
  --radio mock
```
- 기대 결과: `out/dataset_raw.jsonl`이 생성된다.

## 설정
RunSpec 스키마는 `loralink_mllc/config/runspec.py`에 정의돼 있다. 환경변수는 현재 사용하지 않는다.

| 이름 | 기본값 | 필수 여부 | 설명 | 예시 |
| --- | --- | --- | --- | --- |
| run_id | 없음 | 필수 | 런 식별자 | example_raw |
| role | 없음 | 필수 | tx 또는 rx | tx |
| mode | 없음 | 필수 | RAW 또는 LATENT | RAW |
| codec.id | 없음 | 필수 | 코덱 선택 | sensor12_packed |
| window.dims | 12 | 선택 | 센서 차원 수 | 12 |
| window.W | 없음 | 필수 | 윈도우 길이 | 1 |
| window.stride | 1 | 선택 | 윈도우 stride | 1 |
| tx.ack_timeout_ms | auto | 필수 | ACK 타임아웃(ms). `auto`/`null` 지원 | auto |
| tx.max_retries | 없음 | 필수 | 최대 재시도 | 0 |
| max_payload_bytes | 238 | 선택 | payload 상한 | 238 |
| artifacts_manifest | 없음 | 선택 | artifacts manifest 경로 | configs/examples/artifacts_sensor12_packed.json |

설정 파일 위치:
- `configs/examples/tx_raw.yaml`, `configs/examples/rx_raw.yaml`
- `configs/examples/tx_latent.yaml`, `configs/examples/rx_latent.yaml`
- `configs/examples/tx_bam.yaml`, `configs/examples/rx_bam.yaml`
- `configs/examples/artifacts_sensor12_packed.json` (RAW baseline)
- `configs/examples/artifacts.json` (legacy raw:int16 baseline)
- `configs/examples/artifacts_zlib.json`, `configs/examples/artifacts_bam.json`
- `configs/examples/bam_manifest.json`
- `configs/examples/phy_profiles.yaml`

## 아키텍처
```mermaid
flowchart LR
  subgraph TX[TX node]
    Sensor[Sensor window] --> Encode[Codec: RAW | Zlib | BAM]
    Encode --> Packetize[Packetize LEN|SEQ|PAYLOAD]
    Packetize --> UART_TX[UART -> E22]
    UART_TX --> LogTX[JSONL log]
  end

  UART_TX --> Air[LoRa air link]

  subgraph RX[RX node]
    Air --> UART_RX[UART <- E22]
    UART_RX --> Parse[Parse frame]
    Parse --> Decode[Decode / reconstruct]
    Decode --> LogRX[JSONL log]
  end

  subgraph Offline[Offline training loop]
    Data[OTA dataset] --> Train[Train BAM-family model]
    Train --> Artifacts[Artifacts: model + norm + schema]
  end

  Artifacts -.-> Encode
  Artifacts -.-> Decode
```
- TX는 샘플러에서 윈도우를 만들고 코덱으로 payload를 만든다.
- 프레임은 `LEN|SEQ|PAYLOAD`로 고정되며 `max_payload_bytes`를 넘지 않는다.
- RX는 프레임을 파싱하고 LATENT 모드에서만 복원을 시도한다.
- ToA는 AUX 없이 추정되며 TX 게이팅에 사용된다.
- BAM 학습은 Phase 2 오프라인 스크립트로 baseline 워크플로를 제공하며, 생성된 artifacts를 런타임에서 로딩한다.

## 개발
```bash
python -m pip install -e .[dev]
python -m pytest
ruff check .
```
UART/BAM 옵션은 필요 시 설치한다.
```bash
python -m pip install -e .[uart]
python -m pip install -e .[bam]
python -m pip install -e .[viz]
```

Phase 3/4 결과 플롯(선택):
```bash
python scripts/plot_phase_results.py --phase3 out/phase3/report_all.json --out-dir out/plots --plots
```

## 문서와 정책
<details>
<summary>문서 지도</summary>

- `START_HERE.md`: CLI 시작 가이드
- `docs/01_design_doc_experiment_plan.md`: 실험 설계 및 로그 스키마
- `docs/protocol_packet_format.md`: `LEN|SEQ|PAYLOAD` 규격
- `docs/radio_constraints_e22.md`: E22 UART 제약 및 HAT 인터페이스 한계
- `docs/toa_estimation.md`: ToA 추정 공식
- `docs/sensing_pipeline.md`: 센서 입력 스키마
- `docs/phase2_bam_training.md`: BAM 학습 산출물 계약
- `docs/phase3_on_air_validation.md`: Phase 3 on-air 검증 런북
- `docs/phase4_energy_evaluation.md`: Phase 4 에너지 평가 런북
- `docs/review_checklist.md`: 목표 정합성/전면 검토 체크리스트
</details>

- Contributing: `CONTRIBUTING.md`
- Security: `SECURITY.md`
- License: `LICENSE_TODO.md` (미결정)

## 용어 표준화
| 영문 용어 | 한국어 표기/설명 |
| --- | --- |
| RunSpec | 실행 설정 파일(YAML/JSON) |
| Artifacts Manifest | artifacts manifest(코덱 메타데이터 JSON) |
| payload_bytes | payload_bytes(`LEN`) |
| ToA | Time-on-Air(ToA) |
| PDR | Packet Delivery Ratio(PDR) |
| ETX | Expected Transmission Count(ETX) |
| RAW/LATENT | RAW/LATENT 모드 |
| BAM | BAM(코덱/모델 이름) |
| LPWA | LPWA(Low Power Wide Area) |
